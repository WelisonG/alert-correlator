import unittest
from datetime import datetime
from models import Ticket
from correlator import correlate


class TestCorrelator(unittest.TestCase):

    def test_ativo_servico_sintoma_comum(self):
        """Caso 1: Mesmo ativo + serviço + sintoma comum = 80, correlacionado."""
        t1 = Ticket(
            id="T1",
            ativo="APP-001",
            serviço="Payment Service",
            sintomas=["timeout", "high latency"]
        )
        t2 = Ticket(
            id="T2",
            ativo="APP-001",
            serviço="Payment Service",
            sintomas=["timeout", "connection error"]
        )
        result = correlate(t1, t2)
        self.assertEqual(result.score, 80)
        self.assertTrue(result.correlacionado)

    def test_ativo_sintoma_sem_servico(self):
        """Caso 2: Apenas ativo + sintoma comum = 50, não correlacionado."""
        t1 = Ticket(
            id="T1",
            ativo="APP-001",
            sintomas=["timeout"]
        )
        t2 = Ticket(
            id="T2",
            ativo="APP-001",
            sintomas=["timeout"]
        )
        result = correlate(t1, t2)
        self.assertEqual(result.score, 50)
        self.assertFalse(result.correlacionado)

    def test_ativo_servico_sem_temporal(self):
        """Caso 3: Mesmo ativo + serviço, sem proximidade temporal = 60, correlacionado."""
        t1 = Ticket(
            id="T1",
            ativo="APP-001",
            serviço="Payment Service",
            timestamp=datetime(2026, 10, 14, 10, 0, 0)
        )
        t2 = Ticket(
            id="T2",
            ativo="APP-001",
            serviço="Payment Service",
            timestamp=datetime(2026, 10, 14, 10, 15, 0)  # 15 min depois
        )
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertTrue(result.correlacionado)

    def test_apenas_descricao_similar(self):
        """Caso 4: Apenas descrição similar = 10, não correlacionado."""
        t1 = Ticket(
            id="T1",
            descrição="Database connection is failing"
        )
        t2 = Ticket(
            id="T2",
            descrição="Database connection is failing!"
        )
        result = correlate(t1, t2)
        self.assertEqual(result.score, 10)
        self.assertFalse(result.correlacionado)

    def test_apenas_temporal_ativos_diferentes(self):
        """Caso 5: Apenas proximidade temporal, ativos diferentes = 10, não correlacionado."""
        t1 = Ticket(
            id="T1",
            ativo="APP-001",
            timestamp=datetime(2026, 10, 14, 10, 0, 0)
        )
        t2 = Ticket(
            id="T2",
            ativo="APP-002",
            timestamp=datetime(2026, 10, 14, 10, 5, 0)
        )
        result = correlate(t1, t2)
        self.assertEqual(result.score, 10)
        self.assertFalse(result.correlacionado)

    def test_campos_ausentes_sem_excecao(self):
        """Caso 6: Campos opcionais ausentes não causam exceção."""
        t1 = Ticket(id="T1")
        t2 = Ticket(id="T2")
        result = correlate(t1, t2)
        self.assertEqual(result.score, 0)
        self.assertFalse(result.correlacionado)

    def test_score_exatamente_60(self):
        """Caso 7: Score exatamente 60 = correlacionado (boundary)."""
        t1 = Ticket(
            id="T1",
            ativo="APP-001",
            serviço="Payment Service"
        )
        t2 = Ticket(
            id="T2",
            ativo="APP-001",
            serviço="Payment Service"
        )
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertTrue(result.correlacionado)


if __name__ == "__main__":
    unittest.main()
