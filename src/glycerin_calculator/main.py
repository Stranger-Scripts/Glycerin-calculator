"""
glycerin_calculator.main
~~~~~~~~~~~~~~~~~~~~~~~~
FastAPI application.  Two endpoints:

  GET  /          → full page (Jinja2)
  POST /calculate → HTMX partial (result panel + chart JSON)
"""

from __future__ import annotations

#import json
from pathlib import Path
from typing import Annotated

import plotly.graph_objects as go
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from glycerin_calculator.physics import calculate, calculate_batch, viscosity_curve

BASE = Path(__file__).parent
app = FastAPI(title="Glycerin Calculator")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def _build_chart(T: float, wf: float | None, target_mu: float | None) -> str:
    """Return a Plotly figure as a JSON string for the front-end."""
    curve = viscosity_curve(T)
    pcts = [p["pct"] for p in curve]
    mus  = [p["mu"]  for p in curve]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=pcts, y=mus,
        mode="lines",
        line=dict(color="#1f6b6b", width=2.5),
        name="η(glycerol)",
        hovertemplate="%{x:.1f}% → %{y:.2f} mPa·s<extra></extra>",
    ))

    if wf is not None and target_mu is not None:
        fig.add_trace(go.Scatter(
            x=[wf * 100], y=[target_mu],
            mode="markers",
            marker=dict(color="#b8541f", size=10, line=dict(color="white", width=2)),
            name="Target",
            hovertemplate=f"{wf*100:.1f}% → {target_mu:.1f} mPa·s<extra></extra>",
        ))

    fig.update_layout(
        margin=dict(l=48, r=12, t=12, b=36),
        paper_bgcolor="#fbf8f1",
        plot_bgcolor="#fbf8f1",
        xaxis=dict(
            title="Glycerol (% w/w)", ticksuffix="%",
            gridcolor="#d8cfbe", tickfont=dict(family="IBM Plex Mono", size=10),
        ),
        yaxis=dict(
            title="η (mPa·s)", type="log",
            gridcolor="#d8cfbe", tickfont=dict(family="IBM Plex Mono", size=10),
        ),
        showlegend=False,
        font=dict(family="IBM Plex Sans", color="#1d1a17"),
        height=220,
    )
    return fig.to_json()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    chart_json = _build_chart(20.0, None, None)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"chart_json": chart_json},
    )


@app.post("/calculate", response_class=HTMLResponse)
async def calculate_endpoint(
    request: Request,
    target_mu: Annotated[float, Form()],
    temperature: Annotated[float, Form()],
    volume: Annotated[float, Form()],
    w0_pct: Annotated[float, Form()],
    stock_pct: Annotated[float, Form()],
    basis: Annotated[str, Form()],
    mode: Annotated[str, Form()] = "solve",
    final_volume: Annotated[float, Form()] = 0.0,
) -> HTMLResponse:
    if mode == "batch":
        result = calculate_batch(
            target_mu=target_mu,
            T=temperature,
            V_final=final_volume,
            w0_pct=w0_pct,
            stock_pct=stock_pct,
            basis=basis,
        )
    else:
        result = calculate(
            target_mu=target_mu,
            T=temperature,
            V0=volume,
            w0_pct=w0_pct,
            stock_pct=stock_pct,
            basis=basis,
        )

    chart_json = _build_chart(
        temperature,
        wf=result.wf if not result.error else None,
        target_mu=target_mu if not result.error else None,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/result.html",
        context={"r": result, "chart_json": chart_json},
    )


def run() -> None:
    uvicorn.run("glycerin_calculator.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
