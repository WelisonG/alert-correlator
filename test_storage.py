import unittest
import sqlite3
import tempfile
from datetime import datetime
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


if __name__ == "__main__":
    unittest.main()
