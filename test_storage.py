import unittest
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


if __name__ == "__main__":
    unittest.main()
