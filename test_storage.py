import unittest
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from models import Ticket, CorrelationResult, CorrelationReason
import storage


class TestStorage(unittest.TestCase):

    def setUp(self):
        """Cria um banco temporário isolado para cada teste."""
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_path = Path(self.temp_file.name)
        self.temp_file.close()

        self.original_db_path = storage._db_path
        storage._db_path = lambda: self.temp_path
        storage.init_db()

    def tearDown(self):
        """Remove o banco temporário."""
        storage._db_path = self.original_db_path
        if self.temp_path.exists():
            self.temp_path.unlink()

    def test_init_db_criacao_e_reinicializacao(self):
        """Teste 1: Criar tabelas e reinicializar sem erro."""
        storage.init_db()
        storage.init_db()
        tickets = storage.list_tickets()
        self.assertEqual(len(tickets), 0)

    def test_salvar_recuperar_ticket_com_timestamp_sintomas(self):
        """Teste 2: Salvar e recuperar ticket com timestamp e sintomas."""
        t = Ticket(
            id="T001",
            ativo="APP-001",
            serviço="Payment",
            sintomas=["timeout", "error"],
            timestamp=datetime(2026, 10, 14, 10, 30, 0)
        )
        self.assertTrue(storage.save_ticket(t))

        retrieved = storage.get_ticket("T001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.ativo, "APP-001")
        self.assertEqual(retrieved.sintomas, ["timeout", "error"])
        self.assertEqual(retrieved.timestamp, datetime(2026, 10, 14, 10, 30, 0))

    def test_recusar_ticket_duplicado(self):
        """Teste 3: Recusar ticket duplicado sem sobrescrever."""
        t1 = Ticket(id="T001", ativo="APP-001")
        t2 = Ticket(id="T001", ativo="APP-999")

        self.assertTrue(storage.save_ticket(t1))
        self.assertFalse(storage.save_ticket(t2))

        retrieved = storage.get_ticket("T001")
        self.assertEqual(retrieved.ativo, "APP-001")

    def test_diferenciar_none_lista_vazia_sintomas(self):
        """Teste 4: Diferenciar None de lista vazia em sintomas."""
        t_none = Ticket(id="T001", sintomas=None)
        t_empty = Ticket(id="T002", sintomas=[])

        storage.save_ticket(t_none)
        storage.save_ticket(t_empty)

        r_none = storage.get_ticket("T001")
        r_empty = storage.get_ticket("T002")

        self.assertIsNone(r_none.sintomas)
        self.assertEqual(r_empty.sintomas, [])

    def test_salvar_recuperar_correlacao_order_agnostic(self):
        """Teste 5: Salvar e recuperar correlação, mesmo com IDs em ordem inversa."""
        t1 = Ticket(id="T001")
        t2 = Ticket(id="T002")
        storage.save_ticket(t1)
        storage.save_ticket(t2)

        result = CorrelationResult(
            ticket1_id="T001",
            ticket2_id="T002",
            score=80,
            reasons=[CorrelationReason(tipo="ativo", peso=30, explicação="test")],
            correlacionado=True
        )
        self.assertTrue(storage.save_correlation(result))

        retrieved_forward = storage.get_correlation("T001", "T002")
        retrieved_backward = storage.get_correlation("T002", "T001")

        self.assertIsNotNone(retrieved_forward)
        self.assertIsNotNone(retrieved_backward)
        self.assertEqual(retrieved_forward.score, 80)
        self.assertEqual(retrieved_backward.score, 80)

    def test_recusar_correlacao_duplicada_e_referencia_invalida(self):
        """Teste 6: Recusar correlação duplicada e com ticket inexistente."""
        t1 = Ticket(id="T001")
        storage.save_ticket(t1)

        result = CorrelationResult(
            ticket1_id="T001",
            ticket2_id="T002",
            score=50,
            reasons=[],
            correlacionado=False
        )

        self.assertFalse(storage.save_correlation(result))

        t2 = Ticket(id="T002")
        storage.save_ticket(t2)

        self.assertTrue(storage.save_correlation(result))
        self.assertFalse(storage.save_correlation(result))

    def _criar_banco_antigo(self):
        """Recria o arquivo temporário com o schema anterior ao ciclo de vida e um ticket."""
        self.temp_path.unlink()
        conn = sqlite3.connect(str(self.temp_path))
        conn.execute("""
            CREATE TABLE tickets (
                id TEXT PRIMARY KEY,
                ativo TEXT,
                servico TEXT,
                sintomas TEXT,
                descricao TEXT,
                timestamp TEXT,
                criado_em TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO tickets (id, ativo, servico, sintomas, descricao, timestamp, criado_em) "
            "VALUES ('T001', 'APP-001', 'Payment', NULL, NULL, NULL, '2026-10-14T10:00:00')"
        )
        conn.commit()
        conn.close()

    def test_migracao_banco_antigo_preserva_dados(self):
        """Teste 7: Migrar banco sem colunas de ciclo de vida preservando os tickets."""
        self._criar_banco_antigo()
        storage.init_db()

        retrieved = storage.get_ticket("T001")
        self.assertEqual(retrieved.ativo, "APP-001")
        self.assertEqual(retrieved.status, "aberto")
        self.assertIsNone(retrieved.resolvido_em)
        self.assertIsNone(retrieved.encerrado_em)

    def test_migracao_idempotente(self):
        """Teste 8: Executar a migração repetidamente não duplica colunas nem falha."""
        self._criar_banco_antigo()
        storage.init_db()
        storage.init_db()

        conn = sqlite3.connect(str(self.temp_path))
        colunas = [row[1] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()]
        conn.close()
        self.assertEqual(colunas.count("status"), 1)
        self.assertEqual(len(colunas), len(set(colunas)))

    def test_status_padrao_aberto(self):
        """Teste 9: Ticket sem status recebe 'aberto' e datas vazias."""
        storage.save_ticket(Ticket(id="T001"))

        retrieved = storage.get_ticket("T001")
        self.assertEqual(retrieved.status, "aberto")
        self.assertIsNone(retrieved.resolvido_em)
        self.assertIsNone(retrieved.encerrado_em)

    def test_persistir_status_e_resolvido_em(self):
        """Teste 10: Salvar e recuperar status e data compatíveis."""
        t = Ticket(id="T001", status="resolvido", resolvido_em=datetime(2026, 10, 14, 12, 0, 0))
        storage.save_ticket(t)

        retrieved = storage.get_ticket("T001")
        self.assertEqual(retrieved.status, "resolvido")
        self.assertEqual(retrieved.resolvido_em, datetime(2026, 10, 14, 12, 0, 0))
        self.assertIsNone(retrieved.encerrado_em)

    def test_recusar_status_invalido(self):
        """Teste 11: Recusar status fora da lista permitida, no modelo e na atualização."""
        with self.assertRaises(ValueError):
            Ticket(id="T001", status="novo")

        storage.save_ticket(Ticket(id="T001"))
        with self.assertRaises(ValueError):
            storage.atualizar_status_ticket("T001", "novo")

    def test_atualizar_status_ticket(self):
        """Teste 12: Atualizar status de ticket existente e recusar ID inexistente."""
        storage.save_ticket(Ticket(id="T001"))

        self.assertTrue(storage.atualizar_status_ticket("T001", "em_andamento"))
        self.assertEqual(storage.get_ticket("T001").status, "em_andamento")

        self.assertFalse(storage.atualizar_status_ticket("T999", "resolvido"))

    def test_encerrar_preserva_data_de_resolucao(self):
        """Teste 13: Encerrar sem informar resolvido_em mantém a data de resolução já gravada."""
        storage.save_ticket(Ticket(id="T001"))
        resolvido = datetime(2026, 10, 14, 12, 0, 0)
        encerrado = datetime(2026, 10, 15, 9, 0, 0)

        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=resolvido)
        storage.atualizar_status_ticket("T001", "encerrado", encerrado_em=encerrado)

        retrieved = storage.get_ticket("T001")
        self.assertEqual(retrieved.status, "encerrado")
        self.assertEqual(retrieved.resolvido_em, resolvido)
        self.assertEqual(retrieved.encerrado_em, encerrado)

    def _historico(self, ticket_id):
        """Retorna as linhas do histórico de um ticket, em ordem de inserção."""
        conn = sqlite3.connect(str(self.temp_path))
        rows = conn.execute(
            "SELECT status_anterior, status_novo, resolvido_em, encerrado_em FROM ticket_historico WHERE ticket_id = ? ORDER BY id",
            (ticket_id,)
        ).fetchall()
        conn.close()
        return rows

    def test_criacao_registra_evento_inicial(self):
        """Teste 14: save_ticket grava a linha inicial do histórico."""
        storage.save_ticket(Ticket(id="T001", status="em_andamento"))
        self.assertEqual(self._historico("T001"), [(None, "em_andamento", None, None)])

    def test_sequencia_valida_gera_um_evento_por_mudanca(self):
        """Teste 15: aberto -> em_andamento -> resolvido -> encerrado gera uma linha por passo."""
        storage.save_ticket(Ticket(id="T001"))
        storage.atualizar_status_ticket("T001", "em_andamento")
        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=datetime(2026, 10, 14, 12, 0, 0))
        storage.atualizar_status_ticket("T001", "encerrado", encerrado_em=datetime(2026, 10, 15, 9, 0, 0))

        historico = self._historico("T001")
        self.assertEqual([(a, n) for a, n, _, _ in historico], [
            (None, "aberto"), ("aberto", "em_andamento"), ("em_andamento", "resolvido"), ("resolvido", "encerrado")
        ])

    def test_aberto_para_resolvido_direto(self):
        """Teste 16: aberto -> resolvido é transição válida."""
        storage.save_ticket(Ticket(id="T001"))
        self.assertTrue(storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=datetime(2026, 10, 14, 12, 0, 0)))
        self.assertEqual(storage.get_ticket("T001").status, "resolvido")

    def test_reabertura_limpa_resolucao_atual_e_preserva_historico(self):
        """Teste 17: reabrir limpa resolvido_em; cada resolução fica no histórico com sua data."""
        storage.save_ticket(Ticket(id="T001"))
        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=datetime(2026, 10, 14, 12, 0, 0))
        storage.atualizar_status_ticket("T001", "em_andamento")

        reaberto = storage.get_ticket("T001")
        self.assertEqual(reaberto.status, "em_andamento")
        self.assertIsNone(reaberto.resolvido_em)

        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=datetime(2026, 10, 16, 12, 0, 0))
        self.assertEqual(storage.get_ticket("T001").resolvido_em, datetime(2026, 10, 16, 12, 0, 0))

        datas = [resolvido for _, novo, resolvido, _ in self._historico("T001") if novo == "resolvido"]
        self.assertEqual(datas, [
            datetime(2026, 10, 14, 12, 0, 0).isoformat(),
            datetime(2026, 10, 16, 12, 0, 0).isoformat(),
        ])

    def test_encerrar_preserva_ultima_resolucao(self):
        """Teste 18: encerrar mantém a resolução atual e grava encerrado_em no evento."""
        storage.save_ticket(Ticket(id="T001"))
        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=datetime(2026, 10, 16, 12, 0, 0))
        storage.atualizar_status_ticket("T001", "encerrado", encerrado_em=datetime(2026, 10, 17, 9, 0, 0))

        retrieved = storage.get_ticket("T001")
        self.assertEqual(retrieved.resolvido_em, datetime(2026, 10, 16, 12, 0, 0))
        self.assertEqual(retrieved.encerrado_em, datetime(2026, 10, 17, 9, 0, 0))
        self.assertEqual(self._historico("T001")[-1][3], datetime(2026, 10, 17, 9, 0, 0).isoformat())

    def test_evento_em_difere_de_resolvido_em(self):
        """Teste 19: evento_em é o registro em UTC; resolvido_em é a data informada, sem conversão."""
        storage.save_ticket(Ticket(id="T001"))
        resolvido = datetime(2026, 10, 14, 12, 0, 0)
        antes = datetime.now(timezone.utc)
        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=resolvido)
        depois = datetime.now(timezone.utc)

        ticket_resolvido = storage.get_ticket("T001").resolvido_em
        self.assertEqual(ticket_resolvido, resolvido)
        self.assertIsNone(ticket_resolvido.tzinfo)

        conn = sqlite3.connect(str(self.temp_path))
        evento_em = conn.execute(
            "SELECT evento_em FROM ticket_historico WHERE ticket_id = ? AND status_novo = 'resolvido'", ("T001",)
        ).fetchone()[0]
        conn.close()

        evento = datetime.fromisoformat(evento_em)
        self.assertIsNotNone(evento.tzinfo)
        self.assertLessEqual(antes, evento)
        self.assertLessEqual(evento, depois)

    def test_resolucao_sem_data_usa_momento_utc(self):
        """Teste 20: resolver sem informar resolvido_em grava o momento atual em UTC, com fuso."""
        storage.save_ticket(Ticket(id="T001"))
        storage.atualizar_status_ticket("T001", "resolvido")

        resolvido = storage.get_ticket("T001").resolvido_em
        self.assertIsNotNone(resolvido.tzinfo)
        self.assertEqual(resolvido.utcoffset(), timedelta(0))
        self.assertLess(abs(datetime.now(timezone.utc) - resolvido), timedelta(minutes=1))

    def test_transicoes_invalidas_nao_alteram_ticket_nem_historico(self):
        """Teste 21: encerrado é terminal; mesmo status é recusado."""
        storage.save_ticket(Ticket(id="T001"))
        storage.atualizar_status_ticket("T001", "resolvido", resolvido_em=datetime(2026, 10, 14, 12, 0, 0))
        storage.atualizar_status_ticket("T001", "encerrado", encerrado_em=datetime(2026, 10, 15, 9, 0, 0))
        historico_antes = len(self._historico("T001"))

        for novo in ("em_andamento", "resolvido", "encerrado"):
            with self.assertRaises(ValueError):
                storage.atualizar_status_ticket("T001", novo)

        storage.save_ticket(Ticket(id="T002"))
        with self.assertRaises(ValueError):
            storage.atualizar_status_ticket("T002", "aberto")

        self.assertEqual(storage.get_ticket("T001").status, "encerrado")
        self.assertEqual(len(self._historico("T001")), historico_antes)

    def test_falha_no_historico_faz_rollback_do_ticket(self):
        """Teste 22: se o histórico falhar, o status do ticket não muda."""
        storage.save_ticket(Ticket(id="T001"))
        conn = sqlite3.connect(str(self.temp_path))
        conn.execute("""
            CREATE TRIGGER falha_historico BEFORE INSERT ON ticket_historico
            BEGIN SELECT RAISE(ABORT, 'falha simulada'); END
        """)
        conn.commit()
        conn.close()

        with self.assertRaises(sqlite3.DatabaseError):
            storage.atualizar_status_ticket("T001", "em_andamento")

        self.assertEqual(storage.get_ticket("T001").status, "aberto")
        self.assertEqual(len(self._historico("T001")), 1)

    def test_banco_antigo_nao_recebe_eventos_inventados(self):
        """Teste 23: ticket legado não tem histórico após a migração; o primeiro evento é o da próxima mudança."""
        self._criar_banco_antigo()
        storage.init_db()
        storage.init_db()

        self.assertEqual(self._historico("T001"), [])
        storage.atualizar_status_ticket("T001", "em_andamento")
        self.assertEqual([(a, n) for a, n, _, _ in self._historico("T001")], [("aberto", "em_andamento")])


if __name__ == "__main__":
    unittest.main()
