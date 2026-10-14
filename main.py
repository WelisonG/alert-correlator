from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from models import Ticket, CorrelationReason
from correlator import correlate
from storage import init_db, save_ticket, get_ticket, list_tickets, save_correlation, list_correlations


app = FastAPI(title="Alert Correlator")


class TicketInput(BaseModel):
    id: str
    ativo: Optional[str] = None
    servico: Optional[str] = None
    sintomas: Optional[List[str]] = None
    descricao: Optional[str] = None
    timestamp: Optional[datetime] = None


class CorrelationReasonOutput(BaseModel):
    tipo: str
    peso: int
    explicacao: str


class CorrelationOutput(BaseModel):
    ticket1_id: str
    ticket2_id: str
    score: int
    correlacionado: bool
    reasons: List[CorrelationReasonOutput]


class TicketOutput(BaseModel):
    id: str
    ativo: Optional[str] = None
    servico: Optional[str] = None
    sintomas: Optional[List[str]] = None
    descricao: Optional[str] = None
    timestamp: Optional[str] = None

    @classmethod
    def from_ticket(cls, ticket: Ticket):
        return cls(
            id=ticket.id,
            ativo=ticket.ativo,
            servico=ticket.serviço,
            sintomas=ticket.sintomas,
            descricao=ticket.descrição,
            timestamp=ticket.timestamp.isoformat() if ticket.timestamp else None
        )


class PostTicketResponse(BaseModel):
    id: str
    salvo: bool
    msg: str
    correlacoes_encontradas: Optional[int] = None


@app.on_event("startup")
async def startup_event():
    init_db()


@app.post("/tickets")
def create_ticket(ticket_input: TicketInput) -> PostTicketResponse:
    ticket = Ticket(
        id=ticket_input.id,
        ativo=ticket_input.ativo,
        serviço=ticket_input.servico,
        sintomas=ticket_input.sintomas,
        descrição=ticket_input.descricao,
        timestamp=ticket_input.timestamp
    )

    if not save_ticket(ticket):
        return PostTicketResponse(
            id=ticket_input.id,
            salvo=False,
            msg="ID já existe"
        )

    correlacoes_encontradas = 0
    existing_tickets = list_tickets()

    for existing in existing_tickets:
        if existing.id == ticket.id:
            continue

        result = correlate(ticket, existing)
        if result.score >= 60:
            save_correlation(result)
            correlacoes_encontradas += 1

    return PostTicketResponse(
        id=ticket_input.id,
        salvo=True,
        msg="Salvo",
        correlacoes_encontradas=correlacoes_encontradas
    )


@app.get("/tickets")
def list_all_tickets() -> List[TicketOutput]:
    tickets = list_tickets()
    return [TicketOutput.from_ticket(t) for t in tickets]


@app.get("/tickets/{ticket_id}")
def get_ticket_by_id(ticket_id: str) -> TicketOutput:
    ticket = get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket não encontrado")
    return TicketOutput.from_ticket(ticket)


@app.get("/correlations")
def list_all_correlations() -> List[CorrelationOutput]:
    correlations = list_correlations()
    results = []
    for corr in correlations:
        reasons = [
            CorrelationReasonOutput(
                tipo=r.tipo,
                peso=r.peso,
                explicacao=r.explicação
            )
            for r in corr.reasons
        ]
        results.append(CorrelationOutput(
            ticket1_id=corr.ticket1_id,
            ticket2_id=corr.ticket2_id,
            score=corr.score,
            correlacionado=corr.correlacionado,
            reasons=reasons
        ))
    return results


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
