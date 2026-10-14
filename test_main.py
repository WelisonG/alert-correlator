import unittest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
import storage


class TestMain(unittest.TestCase):

    def setUp(self):
        """Cria um banco temporário isolado para cada teste."""
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_path = Path(self.temp_file.name)
        self.temp_file.close()

        self.original_db_path = storage._db_path
        storage._db_path = lambda: self.temp_path
        storage.init_db()

        self.client = TestClient(app)

    def tearDown(self):
        """Remove o banco temporário."""
        storage._db_path = self.original_db_path
        if self.temp_path.exists():
            self.temp_path.unlink()

    def test_post_tickets_salva_corretamente(self):
        """Teste 1: POST /tickets salva um chamado corretamente."""
        payload = {
            "id": "T001",
            "ativo": "APP-001",
            "servico": "Payment"
        }
        response = self.client.post("/tickets", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["salvo"])
        self.assertEqual(data["msg"], "Salvo")
        self.assertEqual(data["id"], "T001")

    def test_dois_chamados_relacionados_geram_correlacao(self):
        """Teste 2: Dois chamados com mesmo ativo e serviço geram sugestão (score 60)."""
        payload1 = {
            "id": "T001",
            "ativo": "APP-001",
            "servico": "Payment"
        }
        payload2 = {
            "id": "T002",
            "ativo": "APP-001",
            "servico": "Payment"
        }

        response1 = self.client.post("/tickets", json=payload1)
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.json()["salvo"])

        response2 = self.client.post("/tickets", json=payload2)
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertTrue(data2["salvo"])
        self.assertEqual(data2["correlacoes_encontradas"], 1)

        corr_response = self.client.get("/correlations")
        correlations = corr_response.json()
        self.assertEqual(len(correlations), 1)
        self.assertEqual(correlations[0]["score"], 60)
        self.assertTrue(correlations[0]["correlacionado"])

    def test_chamado_independente_sem_correlacao(self):
        """Teste 3: Chamado com ativo diferente não gera correlação."""
        payload1 = {
            "id": "T001",
            "ativo": "APP-001",
            "servico": "Payment"
        }
        payload2 = {
            "id": "T002",
            "ativo": "APP-999",
            "servico": "Different"
        }

        self.client.post("/tickets", json=payload1)
        response2 = self.client.post("/tickets", json=payload2)

        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertEqual(data2["correlacoes_encontradas"], 0)

        corr_response = self.client.get("/correlations")
        self.assertEqual(len(corr_response.json()), 0)

    def test_id_duplicado_recusado(self):
        """Teste 4: ID duplicado é recusado sem alterar o original."""
        payload1 = {"id": "T001", "ativo": "APP-001"}
        payload2 = {"id": "T001", "ativo": "APP-999"}

        response1 = self.client.post("/tickets", json=payload1)
        self.assertTrue(response1.json()["salvo"])

        response2 = self.client.post("/tickets", json=payload2)
        self.assertFalse(response2.json()["salvo"])
        self.assertEqual(response2.json()["msg"], "ID já existe")

        get_response = self.client.get("/tickets/T001")
        self.assertEqual(get_response.json()["ativo"], "APP-001")

    def test_get_tickets_lista_e_404_inexistente(self):
        """Teste 5: GET /tickets lista registros e 404 para ID inexistente."""
        payload = {"id": "T001", "ativo": "APP-001"}
        self.client.post("/tickets", json=payload)

        list_response = self.client.get("/tickets")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()), 1)
        self.assertEqual(list_response.json()[0]["id"], "T001")

        not_found = self.client.get("/tickets/T999")
        self.assertEqual(not_found.status_code, 404)

    def test_get_correlations_retorna_sugestoes(self):
        """Teste 6: GET /correlations retorna sugestões armazenadas."""
        payload1 = {"id": "T001", "ativo": "APP-001", "servico": "Payment", "sintomas": ["timeout"]}
        payload2 = {"id": "T002", "ativo": "APP-001", "servico": "Payment", "sintomas": ["timeout"]}

        self.client.post("/tickets", json=payload1)
        self.client.post("/tickets", json=payload2)

        response = self.client.get("/correlations")
        self.assertEqual(response.status_code, 200)
        correlations = response.json()
        self.assertEqual(len(correlations), 1)
        self.assertEqual(correlations[0]["score"], 80)
        self.assertTrue(correlations[0]["correlacionado"])
        self.assertGreater(len(correlations[0]["reasons"]), 0)


if __name__ == "__main__":
    unittest.main()
