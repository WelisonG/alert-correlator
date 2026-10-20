import unittest
from datetime import datetime, timedelta, timezone
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

    def test_incidente_longo_ambos_abertos_correlaciona(self):
        """Caso 8: Dois tickets abertos com 5 horas de diferença continuam correlacionáveis."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 13, 0, 0, tzinfo=timezone.utc))
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertTrue(result.correlacionado)

    def test_ticket_resolvido_antes_do_novo_nao_correlaciona(self):
        """Caso 9: Período resolvido antes do início do outro ticket bloqueia a correlação, com score preservado."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="resolvido",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc),
                    resolvido_em=datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc))
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertFalse(result.correlacionado)

    def test_encerramento_administrativo_nao_estende_periodo(self):
        """Caso 10: encerrado_em horas depois não estende o período; o fim é resolvido_em."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="encerrado",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc),
                    resolvido_em=datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc),
                    encerrado_em=datetime(2026, 10, 14, 17, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertFalse(result.correlacionado)

    def test_encerrado_sem_resolvido_em_e_indeterminado(self):
        """Caso 11: Sem resolvido_em, o período é indeterminado e a decisão segue a pontuação."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="encerrado",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc),
                    encerrado_em=datetime(2026, 10, 14, 17, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc))
        result = correlate(t1, t2)
        self.assertTrue(result.correlacionado)

    def test_datas_naive_nao_bloqueiam(self):
        """Caso 12: Datas naive não geram bloqueio temporal."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="resolvido",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0),
                    resolvido_em=datetime(2026, 10, 14, 9, 0, 0))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 10, 0, 0))
        result = correlate(t1, t2)
        self.assertTrue(result.correlacionado)

    def test_fusos_diferentes_representam_mesmo_instante(self):
        """Caso 13: Datas com fusos diferentes são comparadas como instantes."""
        fuso_sp = timezone(timedelta(hours=-3))
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="resolvido",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc),
                    resolvido_em=datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 6, 30, 0, tzinfo=fuso_sp))  # 09:30 UTC
        result = correlate(t1, t2)
        self.assertFalse(result.correlacionado)

    def test_timestamp_misto_nao_causa_excecao(self):
        """Caso 14: Um timestamp naive e outro aware não geram erro nem pontos temporais."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service",
                    timestamp=datetime(2026, 10, 14, 8, 5, 0))
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertTrue(result.correlacionado)

    def test_reabertura_continua_correlacionavel(self):
        """Caso 15: Ticket em andamento sem resolvido_em é tratado como aberto."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="em_andamento",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 15, 0, 0, tzinfo=timezone.utc))
        result = correlate(t1, t2)
        self.assertTrue(result.correlacionado)

    def test_simetria_inversao_de_ordem(self):
        """Caso 16: Inverter os tickets não altera score nem decisão, inclusive no bloqueio."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="resolvido",
                    timestamp=datetime(2026, 10, 14, 8, 0, 0, tzinfo=timezone.utc),
                    resolvido_em=datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc))
        ida = correlate(t1, t2)
        volta = correlate(t2, t1)
        self.assertEqual(ida.score, volta.score)
        self.assertEqual(ida.correlacionado, volta.correlacionado)

    def test_simetria_descricoes(self):
        """Caso 17: A similaridade de descrições não depende da ordem dos tickets."""
        t1 = Ticket(id="T1", descrição="Database connection is failing")
        t2 = Ticket(id="T2", descrição="Database connection is failing!")
        self.assertEqual(correlate(t1, t2).score, correlate(t2, t1).score)

    def test_sintomas_em_comum_ordenados(self):
        """Caso 18: A explicação dos sintomas em comum é determinística."""
        t1 = Ticket(id="T1", sintomas=["b", "a"])
        t2 = Ticket(id="T2", sintomas=["a", "b", "c"])
        result = correlate(t1, t2)
        explicacoes = [r.explicação for r in result.reasons if r.tipo == "sintoma"]
        self.assertEqual(explicacoes, ["Sintomas em comum: a, b"])

    def test_resolucao_anterior_a_abertura_nao_bloqueia(self):
        """Caso 19: Resolução anterior à abertura é inconsistente; não bloqueia e a decisão segue o score."""
        t1 = Ticket(id="T1", ativo="APP-001", serviço="Payment Service", status="resolvido",
                    timestamp=datetime(2026, 10, 14, 10, 0, 0, tzinfo=timezone.utc),
                    resolvido_em=datetime(2026, 10, 14, 9, 0, 0, tzinfo=timezone.utc))
        t2 = Ticket(id="T2", ativo="APP-001", serviço="Payment Service", status="aberto",
                    timestamp=datetime(2026, 10, 14, 11, 0, 0, tzinfo=timezone.utc))
        result = correlate(t1, t2)
        self.assertEqual(result.score, 60)
        self.assertTrue(result.correlacionado)


if __name__ == "__main__":
    unittest.main()
