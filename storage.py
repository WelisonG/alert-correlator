import sqlite3
import json
from datetime import datetime
from pathlib import Path
from models import Ticket, CorrelationResult, CorrelationReason


def _db_path():
    """Retorna o caminho absoluto do banco de dados."""
    return Path(__file__).parent / "alert_correlator.db"


def _get_connection():
    """Abre conexão com o SQLite e habilita chaves estrangeiras."""
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


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
        criado_em = datetime.utcnow().isoformat()

        cursor.execute("""
            INSERT INTO tickets (id, ativo, servico, sintomas, descricao, timestamp, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ticket.id, ticket.ativo, ticket.serviço, sintomas_json, ticket.descrição, timestamp_iso, criado_em))

        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_ticket(id: str) -> Ticket | None:
    """Busca um chamado por ID."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, ativo, servico, sintomas, descricao, timestamp FROM tickets WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    sintomas = json.loads(row[3]) if row[3] else None
    timestamp = datetime.fromisoformat(row[5]) if row[5] else None

    return Ticket(
        id=row[0],
        ativo=row[1],
        serviço=row[2],
        sintomas=sintomas,
        descrição=row[4],
        timestamp=timestamp
    )


def list_tickets() -> list[Ticket]:
    """Lista todos os chamados."""
    conn = _get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, ativo, servico, sintomas, descricao, timestamp FROM tickets")
    rows = cursor.fetchall()
    conn.close()

    tickets = []
    for row in rows:
        sintomas = json.loads(row[3]) if row[3] else None
        timestamp = datetime.fromisoformat(row[5]) if row[5] else None
        tickets.append(Ticket(
            id=row[0],
            ativo=row[1],
            serviço=row[2],
            sintomas=sintomas,
            descrição=row[4],
            timestamp=timestamp
        ))

    return tickets


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
