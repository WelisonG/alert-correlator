import sqlite3
import json
from datetime import datetime
from pathlib import Path
from models import Ticket, CorrelationResult, CorrelationReason, validar_status


def _db_path():
    """Retorna o caminho absoluto do banco de dados."""
    return Path(__file__).parent / "alert_correlator.db"


def _get_connection():
    """Abre conexão com o SQLite e habilita chaves estrangeiras."""
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


COLUNAS_CICLO_VIDA = {
    "status": "TEXT NOT NULL DEFAULT 'aberto'",
    "resolvido_em": "TEXT",
    "encerrado_em": "TEXT",
}

COLUNAS_TICKET = "id, ativo, servico, sintomas, descricao, timestamp, status, resolvido_em, encerrado_em"


def _migrar_tickets(cursor):
    """Adiciona colunas do ciclo de vida em bancos antigos. Idempotente e sem apagar dados."""
    cursor.execute("PRAGMA table_info(tickets)")
    existentes = {row[1] for row in cursor.fetchall()}
    for nome, definicao in COLUNAS_CICLO_VIDA.items():
        if nome not in existentes:
            cursor.execute(f"ALTER TABLE tickets ADD COLUMN {nome} {definicao}")


def init_db():
    """Cria as tabelas se não existirem."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            ativo TEXT,
            servico TEXT,
            sintomas TEXT,
            descricao TEXT,
            timestamp TEXT,
            criado_em TEXT NOT NULL
        )
    """)

    _migrar_tickets(cursor)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket1_id TEXT NOT NULL,
            ticket2_id TEXT NOT NULL,
            score INTEGER NOT NULL,
            reasons TEXT NOT NULL,
            correlacionado INTEGER NOT NULL,
            criado_em TEXT NOT NULL,
            UNIQUE(ticket1_id, ticket2_id),
            FOREIGN KEY(ticket1_id) REFERENCES tickets(id),
            FOREIGN KEY(ticket2_id) REFERENCES tickets(id),
            CHECK(ticket1_id < ticket2_id)
        )
    """)

    conn.commit()
    conn.close()


def save_ticket(ticket: Ticket) -> bool:
    """Salva um novo chamado. Retorna False se ID já existe."""
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        sintomas_json = json.dumps(ticket.sintomas) if ticket.sintomas is not None else None
        timestamp_iso = ticket.timestamp.isoformat() if ticket.timestamp else None
        resolvido_em_iso = ticket.resolvido_em.isoformat() if ticket.resolvido_em else None
        encerrado_em_iso = ticket.encerrado_em.isoformat() if ticket.encerrado_em else None
        criado_em = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO tickets (id, ativo, servico, sintomas, descricao, timestamp, criado_em, status, resolvido_em, encerrado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ticket.id, ticket.ativo, ticket.serviço, sintomas_json, ticket.descrição, timestamp_iso, criado_em,
              ticket.status, resolvido_em_iso, encerrado_em_iso))

        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def _linha_para_ticket(row) -> Ticket:
    """Converte uma linha da tabela tickets (colunas de COLUNAS_TICKET) em Ticket."""
    return Ticket(
        id=row[0],
        ativo=row[1],
        serviço=row[2],
        sintomas=json.loads(row[3]) if row[3] else None,
        descrição=row[4],
        timestamp=datetime.fromisoformat(row[5]) if row[5] else None,
        status=row[6],
        resolvido_em=datetime.fromisoformat(row[7]) if row[7] else None,
        encerrado_em=datetime.fromisoformat(row[8]) if row[8] else None
    )


def get_ticket(id: str) -> Ticket | None:
    """Busca um chamado por ID."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT {COLUNAS_TICKET} FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return _linha_para_ticket(row)


def list_tickets() -> list[Ticket]:
    """Lista todos os chamados."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT {COLUNAS_TICKET} FROM tickets")
    rows = cursor.fetchall()
    conn.close()

    return [_linha_para_ticket(row) for row in rows]


def atualizar_status_ticket(id: str, status: str, resolvido_em: datetime | None = None,
                            encerrado_em: datetime | None = None) -> bool:
    """Atualiza o status de um chamado. Datas omitidas (None) preservam os valores existentes. Retorna False se o ID não existe."""
    validar_status(status)
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE tickets
            SET status = ?,
                resolvido_em = COALESCE(?, resolvido_em),
                encerrado_em = COALESCE(?, encerrado_em)
            WHERE id = ?
        """, (
            status,
            resolvido_em.isoformat() if resolvido_em else None,
            encerrado_em.isoformat() if encerrado_em else None,
            id
        ))
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def save_correlation(result: CorrelationResult) -> bool:
    """Salva um resultado de correlação. Normaliza a ordem dos IDs e evita duplicatas."""
    conn = _get_connection()
    cursor = conn.cursor()

    t1, t2 = sorted([result.ticket1_id, result.ticket2_id])
    reasons_json = json.dumps([{
        "tipo": r.tipo,
        "peso": r.peso,
        "explicacao": r.explicação
    } for r in result.reasons])
    criado_em = datetime.utcnow().isoformat()

    try:
        cursor.execute("""
            INSERT INTO correlations (ticket1_id, ticket2_id, score, reasons, correlacionado, criado_em)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (t1, t2, result.score, reasons_json, int(result.correlacionado), criado_em))

        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_correlation(ticket1_id: str, ticket2_id: str) -> CorrelationResult | None:
    """Busca uma correlação entre dois tickets (order-agnostic)."""
    conn = _get_connection()
    cursor = conn.cursor()

    t1, t2 = sorted([ticket1_id, ticket2_id])

    cursor.execute("""
        SELECT ticket1_id, ticket2_id, score, reasons, correlacionado
        FROM correlations WHERE ticket1_id = ? AND ticket2_id = ?
    """, (t1, t2))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    reasons = [
        CorrelationReason(
            tipo=r["tipo"],
            peso=r["peso"],
            explicação=r["explicacao"]
        )
        for r in json.loads(row[3])
    ]

    return CorrelationResult(
        ticket1_id=row[0],
        ticket2_id=row[1],
        score=row[2],
        reasons=reasons,
        correlacionado=bool(row[4])
    )


def list_correlations() -> list[CorrelationResult]:
    """Lista todas as correlações."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticket1_id, ticket2_id, score, reasons, correlacionado FROM correlations")
    rows = cursor.fetchall()
    conn.close()

    correlations = []
    for row in rows:
        reasons = [
            CorrelationReason(
                tipo=r["tipo"],
                peso=r["peso"],
                explicação=r["explicacao"]
            )
            for r in json.loads(row[3])
        ]
        correlations.append(CorrelationResult(
            ticket1_id=row[0],
            ticket2_id=row[1],
            score=row[2],
            reasons=reasons,
            correlacionado=bool(row[4])
        ))

    return correlations
