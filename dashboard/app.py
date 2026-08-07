"""Streamlit dashboard for audited municipal capacity-priority outputs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.data import (  # noqa: E402
    PROFILE_LABELS,
    REFERENCE_SCENARIO,
    WEIGHT_LABELS,
    load_dashboard_data,
    scenario_label,
    selected_scenario,
    split_scenario,
)

st.set_page_config(
    page_title="Prioridade Municipal · Pará",
    page_icon="🧭",
    layout="wide",
)


@st.cache_data(show_spinner="Validando resultados auditados...")
def get_data():
    return load_dashboard_data(ROOT)


def fmt(value: float, decimals: int = 3) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def scenario_table(data, scenario: str) -> pd.DataFrame:
    current = selected_scenario(data.scenarios, scenario)
    result = current.merge(data.profiles, on=["municipality_code", "municipality"])
    result = result.merge(data.municipalities, on=["municipality_code", "municipality"])
    result["perfil"] = result["priority_stability_profile"].map(PROFILE_LABELS)
    return result.sort_values(["selected_rank", "municipality"], kind="stable")


def statewide_tab(data, scenario: str) -> None:
    frame = scenario_table(data, scenario)
    st.subheader("Visão estadual")
    st.caption("Cada ponto representa a sede de um dos 144 municípios. O mapa não altera os cálculos.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Municípios", len(frame))
    c2.metric("Configurações oficiais", len(data.scenario_names))
    c3.metric("Maior escore", fmt(frame["selected_score"].max()))
    c4.metric("Correlação mínima entre rankings", fmt(data.agreement["rank_correlation"].min()))

    left, right = st.columns([1.45, 1])
    with left:
        fig = px.scatter_map(
            frame,
            lat="latitude",
            lon="longitude",
            color="selected_score",
            size="selected_score",
            hover_name="municipality",
            hover_data={
                "selected_rank": True,
                "selected_score": ":.3f",
                "perfil": True,
                "latitude": False,
                "longitude": False,
            },
            color_continuous_scale="YlOrRd",
            size_max=22,
            zoom=4.2,
            height=620,
            labels={
                "selected_rank": "Posição",
                "selected_score": "Escore",
                "perfil": "Estabilidade",
            },
        )
        fig.update_layout(map_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("##### Ranking da configuração selecionada")
        display = frame[["selected_rank", "municipality", "selected_score", "perfil"]].rename(
            columns={
                "selected_rank": "Posição",
                "municipality": "Município",
                "selected_score": "Escore",
                "perfil": "Estabilidade",
            }
        )
        st.dataframe(
            display,
            hide_index=True,
            use_container_width=True,
            height=500,
            column_config={"Escore": st.column_config.NumberColumn(format="%.3f")},
        )
        st.download_button(
            "Baixar ranking selecionado (CSV)",
            display.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"ranking_{scenario}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def municipal_profile_tab(data, scenario: str) -> None:
    st.subheader("Perfil municipal")
    names = sorted(data.profiles["municipality"].tolist())
    municipality = st.selectbox("Município", names, key="profile_municipality")
    row = scenario_table(data, scenario).set_index("municipality").loc[municipality]
    explanation = data.explanations.set_index("municipality").loc[municipality]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Posição nesta configuração", int(row["selected_rank"]))
    c2.metric("Escore nesta configuração", fmt(row["selected_score"]))
    c3.metric("Melhor–pior posição", f"{int(row['best_priority_rank'])}–{int(row['worst_priority_rank'])}")
    c4.metric("Frequência no quartil superior", f"{100 * row['top_quartile_frequency']:.1f}%")

    left, right = st.columns(2)
    with left:
        contributions = pd.DataFrame(
            {
                "Dimensão": ["Institucional", "Rede de serviços", "Barreira de transporte"],
                "Contribuição média": [
                    explanation["mean_institutional_contribution"],
                    explanation["mean_service_network_contribution"],
                    explanation["mean_transport_barrier_contribution"],
                ],
            }
        )
        fig = px.bar(
            contributions,
            x="Contribuição média",
            y="Dimensão",
            orientation="h",
            color="Dimensão",
            text_auto=".3f",
            title="Contribuição média nas 48 configurações",
        )
        fig.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        ranks = []
        for name in data.scenario_names:
            transport, weight = split_scenario(name)
            ranks.append(
                {
                    "Configuração": scenario_label(name),
                    "Peso macro": WEIGHT_LABELS.get(weight, weight),
                    "Posição": int(
                        data.scenarios.set_index("municipality").loc[municipality, f"{name}__rank"]
                    ),
                    "Transporte": transport,
                }
            )
        rank_frame = pd.DataFrame(ranks).sort_values("Posição")
        fig = px.scatter(
            rank_frame,
            x="Configuração",
            y="Posição",
            color="Peso macro",
            title="Posição nas 48 configurações",
            hover_data=["Configuração"],
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(showticklabels=False, title=None)
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

    st.info(
        f"Perfil de estabilidade: **{PROFILE_LABELS.get(row['priority_stability_profile'], row['priority_stability_profile'])}**. "
        "Esse rótulo resume a robustez entre configurações; não constitui decisão automática de alocação."
    )


def comparison_tab(data, scenario: str) -> None:
    st.subheader("Comparação entre municípios")
    names = sorted(data.profiles["municipality"].tolist())
    selected = st.multiselect(
        "Selecione de 2 a 5 municípios",
        names,
        default=names[:2],
        max_selections=5,
    )
    if len(selected) < 2:
        st.warning("Selecione pelo menos dois municípios.")
        return

    frame = scenario_table(data, scenario)
    compare = frame[frame["municipality"].isin(selected)].copy()
    long = compare.melt(
        id_vars="municipality",
        value_vars=["institutional_deficit", "service_network_deficit", "selected_score"],
        var_name="Indicador",
        value_name="Valor",
    )
    labels = {
        "institutional_deficit": "Déficit institucional",
        "service_network_deficit": "Déficit da rede de serviços",
        "selected_score": "Prioridade na configuração",
    }
    long["Indicador"] = long["Indicador"].map(labels)
    fig = px.bar(
        long,
        x="Indicador",
        y="Valor",
        color="municipality",
        barmode="group",
        range_y=[0, 1],
        labels={"municipality": "Município"},
        title="Dimensões normalizadas e escore selecionado",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(
        compare[
            [
                "municipality",
                "selected_rank",
                "selected_score",
                "best_priority_rank",
                "worst_priority_rank",
                "top_quartile_frequency",
                "perfil",
            ]
        ].rename(
            columns={
                "municipality": "Município",
                "selected_rank": "Posição",
                "selected_score": "Escore",
                "best_priority_rank": "Melhor posição",
                "worst_priority_rank": "Pior posição",
                "top_quartile_frequency": "Frequência no quartil superior",
                "perfil": "Estabilidade",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


def methodology_tab(data) -> None:
    st.subheader("Metodologia, dados e limites")
    st.markdown(
        """
        O dashboard é uma **camada de visualização somente leitura**. Os escores são produzidos
        previamente pelo pipeline auditado e não são recalculados nesta interface. Todos os 144
        municípios recebem o mesmo tratamento metodológico.

        - **Objeto:** prioridade relativa para fortalecimento da capacidade municipal sob restrições
          de acesso multimodal.
        - **Dimensões:** déficit institucional, déficit da rede de serviços e barreira de transporte.
        - **Robustez:** 12 cenários multimodais × 4 configurações de pesos macro = 48 configurações.
        - **Normalização:** posição percentílica dentro da amostra, com média para empates.
        - **Exclusão deliberada:** registros policiais não integram o framework atual.
        - **População:** Censo Demográfico 2022, publicado e processado em 2023.

        Os resultados são instrumentos de apoio à decisão, não estimativas de violência, subnotificação,
        qualidade do serviço, tempo real de viagem ou decisões automáticas de financiamento.
        """
    )
    st.markdown("##### Concordância com a configuração de referência")
    agreement = data.agreement.copy()
    agreement["Configuração"] = agreement["scenario"].map(scenario_label)
    st.dataframe(
        agreement[
            [
                "Configuração",
                "rank_correlation",
                "top_k_overlap_fraction",
                "mean_absolute_rank_shift",
                "maximum_absolute_rank_shift",
            ]
        ].rename(
            columns={
                "rank_correlation": "Correlação de Spearman",
                "top_k_overlap_fraction": "Sobreposição top 10",
                "mean_absolute_rank_shift": "Mudança média de posição",
                "maximum_absolute_rank_shift": "Mudança máxima de posição",
            }
        ),
        hide_index=True,
        use_container_width=True,
    )


try:
    data = get_data()
except (FileNotFoundError, KeyError, ValueError) as exc:
    st.error(f"Falha na validação dos resultados: {exc}")
    st.stop()

st.title("🧭 Prioridade municipal para fortalecimento de capacidades")
st.caption("Pará · 144 municípios · 48 configurações auditadas · visualização somente leitura")

scenario = st.selectbox(
    "Configuração oficial",
    data.scenario_names,
    index=data.scenario_names.index(REFERENCE_SCENARIO),
    format_func=scenario_label,
)

tab_state, tab_profile, tab_compare, tab_method = st.tabs(
    ["Visão estadual", "Perfil municipal", "Comparação", "Metodologia"]
)
with tab_state:
    statewide_tab(data, scenario)
with tab_profile:
    municipal_profile_tab(data, scenario)
with tab_compare:
    comparison_tab(data, scenario)
with tab_method:
    methodology_tab(data)

st.divider()
st.caption(
    "Framework explicável de priorização municipal · resultados oficiais pré-calculados · "
    "nenhum parâmetro pode ser alterado pelo dashboard."
)
