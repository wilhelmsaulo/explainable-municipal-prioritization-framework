"""Bilingual Streamlit dashboard for audited capacity-priority outputs."""

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
    MACRO_WEIGHT_ORDER,
    MACRO_WEIGHTS,
    PROFILE_LABELS,
    REFERENCE_SCENARIO,
    WEIGHT_LABELS,
    compose_scenario,
    load_dashboard_data,
    scenario_label,
    selected_scenario,
    split_scenario,
    transport_label,
    weight_label,
)

TEXT = {
    "en": {
        "page_title": "Municipal Priority · Pará",
        "title": "🧭 Municipal priority for capacity strengthening",
        "caption": "Pará · 144 municipalities · 48 audited configurations · read-only visualization",
        "language": "Language",
        "configuration": "Official configuration",
        "transport_scenario": "Transport submodel scenario",
        "macro_weights_selector": "Macro-dimension weights",
        "framework_dimensions": "Framework dimensions",
        "always_included": "Every final score combines all three macro-dimensions. The transport selector changes only the transport submodel; it does not remove or replace the other dimensions.",
        "institutional_card": "1 · Institutional deficit",
        "institutional_card_body": "Municipal institutional capacity for policies addressing women.",
        "institutional_sources": "Source: MUNIC 2023",
        "service_card": "2 · Service-network deficit",
        "service_card_body": "Health services and professionals, specialized social assistance, justice access, and the specialized protection network.",
        "service_sources": "Sources: CNES, MDS/SNAS, TJPA, and Ligue 180",
        "transport_card": "3 · Transport barrier",
        "transport_card_body": "Road, waterway, and air access represented through 12 predeclared multimodal scenarios.",
        "transport_sources": "Sources: MapBiomas, ANTAQ, and DECEA/ICA",
        "context_note": "IBGE population supports context and denominators where applicable. Police records from 2022–2025 are preserved in the repository but deliberately excluded from this framework.",
        "selected_configuration": "Selected audited configuration",
        "transport_interpretation": "Transport interpretation",
        "macro_weights_detail": "Macro weights",
        "institutional_weight": "institutional",
        "service_weight": "service network",
        "transport_weight": "transport barrier",
        "mode_equal": "transport modes receive equal emphasis",
        "mode_road": "the road mode is emphasized",
        "mode_water": "the waterway mode is emphasized",
        "mode_air": "the air mode is emphasized",
        "role_equal": "availability and proximity receive equal emphasis",
        "role_availability": "availability is emphasized",
        "role_proximity": "proximity is emphasized",
        "state_tab": "Statewide overview",
        "profile_tab": "Municipal profile",
        "compare_tab": "Comparison",
        "method_tab": "Methodology",
        "state_title": "Statewide overview",
        "map_caption": "Each point represents a municipal seat. The map does not alter any calculation.",
        "municipalities": "Municipalities",
        "configurations": "Official configurations",
        "highest_score": "Highest score",
        "minimum_correlation": "Minimum rank correlation",
        "rank_title": "Ranking for the selected configuration",
        "rank": "Rank",
        "municipality": "Municipality",
        "score": "Score",
        "stability": "Stability",
        "download": "Download selected ranking (CSV)",
        "profile_title": "Municipal profile",
        "selected_rank": "Rank in this configuration",
        "selected_score": "Score in this configuration",
        "best_worst": "Best–worst rank",
        "top_quartile": "Top-quartile frequency",
        "dimension": "Dimension",
        "mean_contribution": "Mean contribution",
        "institutional": "Institutional",
        "service_network": "Service network",
        "transport_barrier": "Transport barrier",
        "contribution_title": "Mean contribution across 48 configurations",
        "macro_weight": "Macro weight",
        "rank_48": "Rank across 48 configurations",
        "stability_profile": "Stability profile",
        "stability_note": "This label summarizes robustness across configurations; it is not an automatic allocation decision.",
        "compare_title": "Municipality comparison",
        "choose_municipalities": "Select 2 to 5 municipalities",
        "choose_warning": "Select at least two municipalities.",
        "indicator": "Indicator",
        "value": "Value",
        "institutional_deficit": "Institutional deficit",
        "service_deficit": "Service-network deficit",
        "configuration_priority": "Priority in selected configuration",
        "comparison_chart": "Normalized dimensions and selected score",
        "best_rank": "Best rank",
        "worst_rank": "Worst rank",
        "method_title": "Methodology, data, and limitations",
        "agreement_title": "Agreement with the reference configuration",
        "spearman": "Spearman correlation",
        "top10_overlap": "Top-10 overlap",
        "mean_shift": "Mean absolute rank shift",
        "max_shift": "Maximum absolute rank shift",
        "validation_error": "Result validation failed",
        "footer": "Explainable municipal prioritization framework · official precomputed outputs · dashboard parameters cannot be changed.",
    },
    "pt": {
        "page_title": "Prioridade Municipal · Pará",
        "title": "🧭 Prioridade municipal para fortalecimento de capacidades",
        "caption": "Pará · 144 municípios · 48 configurações auditadas · visualização somente leitura",
        "language": "Idioma",
        "configuration": "Configuração oficial",
        "transport_scenario": "Cenário do submodelo de transporte",
        "macro_weights_selector": "Pesos das macrodimensões",
        "framework_dimensions": "Dimensões do framework",
        "always_included": "Todo escore final combina as três macrodimensões. O seletor de transporte modifica apenas o submodelo de transporte; ele não remove nem substitui as demais dimensões.",
        "institutional_card": "1 · Déficit institucional",
        "institutional_card_body": "Capacidade institucional municipal para políticas destinadas às mulheres.",
        "institutional_sources": "Fonte: MUNIC 2023",
        "service_card": "2 · Déficit da rede de serviços",
        "service_card_body": "Serviços e profissionais de saúde, assistência social especializada, acesso à justiça e rede especializada de proteção.",
        "service_sources": "Fontes: CNES, MDS/SNAS, TJPA e Ligue 180",
        "transport_card": "3 · Barreira de transporte",
        "transport_card_body": "Acesso rodoviário, hidroviário e aéreo representado por 12 cenários multimodais previamente declarados.",
        "transport_sources": "Fontes: MapBiomas, ANTAQ e DECEA/ICA",
        "context_note": "A população do IBGE apoia o contexto e os denominadores quando aplicável. Os registros policiais de 2022–2025 estão preservados no repositório, mas foram deliberadamente excluídos deste framework.",
        "selected_configuration": "Configuração auditada selecionada",
        "transport_interpretation": "Interpretação do transporte",
        "macro_weights_detail": "Pesos macro",
        "institutional_weight": "institucional",
        "service_weight": "rede de serviços",
        "transport_weight": "barreira de transporte",
        "mode_equal": "os modos de transporte recebem igual ênfase",
        "mode_road": "o modo rodoviário recebe maior ênfase",
        "mode_water": "o modo hidroviário recebe maior ênfase",
        "mode_air": "o modo aéreo recebe maior ênfase",
        "role_equal": "disponibilidade e proximidade recebem igual ênfase",
        "role_availability": "a disponibilidade recebe maior ênfase",
        "role_proximity": "a proximidade recebe maior ênfase",
        "state_tab": "Visão estadual",
        "profile_tab": "Perfil municipal",
        "compare_tab": "Comparação",
        "method_tab": "Metodologia",
        "state_title": "Visão estadual",
        "map_caption": "Cada ponto representa a sede municipal. O mapa não altera nenhum cálculo.",
        "municipalities": "Municípios",
        "configurations": "Configurações oficiais",
        "highest_score": "Maior escore",
        "minimum_correlation": "Correlação mínima entre rankings",
        "rank_title": "Ranking da configuração selecionada",
        "rank": "Posição",
        "municipality": "Município",
        "score": "Escore",
        "stability": "Estabilidade",
        "download": "Baixar ranking selecionado (CSV)",
        "profile_title": "Perfil municipal",
        "selected_rank": "Posição nesta configuração",
        "selected_score": "Escore nesta configuração",
        "best_worst": "Melhor–pior posição",
        "top_quartile": "Frequência no quartil superior",
        "dimension": "Dimensão",
        "mean_contribution": "Contribuição média",
        "institutional": "Institucional",
        "service_network": "Rede de serviços",
        "transport_barrier": "Barreira de transporte",
        "contribution_title": "Contribuição média nas 48 configurações",
        "macro_weight": "Peso macro",
        "rank_48": "Posição nas 48 configurações",
        "stability_profile": "Perfil de estabilidade",
        "stability_note": "Este rótulo resume a robustez entre configurações; não constitui decisão automática de alocação.",
        "compare_title": "Comparação entre municípios",
        "choose_municipalities": "Selecione de 2 a 5 municípios",
        "choose_warning": "Selecione pelo menos dois municípios.",
        "indicator": "Indicador",
        "value": "Valor",
        "institutional_deficit": "Déficit institucional",
        "service_deficit": "Déficit da rede de serviços",
        "configuration_priority": "Prioridade na configuração selecionada",
        "comparison_chart": "Dimensões normalizadas e escore selecionado",
        "best_rank": "Melhor posição",
        "worst_rank": "Pior posição",
        "method_title": "Metodologia, dados e limitações",
        "agreement_title": "Concordância com a configuração de referência",
        "spearman": "Correlação de Spearman",
        "top10_overlap": "Sobreposição top 10",
        "mean_shift": "Mudança média absoluta de posição",
        "max_shift": "Mudança máxima absoluta de posição",
        "validation_error": "Falha na validação dos resultados",
        "footer": "Framework explicável de priorização municipal · resultados oficiais pré-calculados · os parâmetros não podem ser alterados.",
    },
}

st.set_page_config(page_title=TEXT["en"]["page_title"], page_icon="🧭", layout="wide")


@st.cache_data(show_spinner="Validating audited outputs...")
def get_data():
    return load_dashboard_data(ROOT)


def fmt(value: float, language: str, decimals: int = 3) -> str:
    rendered = f"{value:.{decimals}f}"
    return rendered.replace(".", ",") if language == "pt" else rendered


def pct(value: float, language: str) -> str:
    rendered = f"{value:.1%}"
    return rendered.replace(".", ",") if language == "pt" else rendered


def framework_dimensions(tx: dict[str, str]) -> None:
    st.subheader(tx["framework_dimensions"])
    st.info(tx["always_included"])
    institutional, services, transport = st.columns(3)
    cards = (
        (
            institutional,
            tx["institutional_card"],
            tx["institutional_card_body"],
            tx["institutional_sources"],
        ),
        (
            services,
            tx["service_card"],
            tx["service_card_body"],
            tx["service_sources"],
        ),
        (
            transport,
            tx["transport_card"],
            tx["transport_card_body"],
            tx["transport_sources"],
        ),
    )
    for column, title, body, sources in cards:
        with column, st.container(border=True):
            st.markdown(f"#### {title}")
            st.write(body)
            st.caption(sources)
    st.caption(tx["context_note"])


def scenario_table(data, scenario: str, language: str) -> pd.DataFrame:
    current = selected_scenario(data.scenarios, scenario)
    result = current.merge(data.profiles, on=["municipality_code", "municipality"])
    result = result.merge(data.municipalities, on=["municipality_code", "municipality"])
    result["profile_label"] = result["priority_stability_profile"].map(PROFILE_LABELS[language])
    return result.sort_values(["selected_rank", "municipality"], kind="stable")


def statewide_tab(data, scenario: str, language: str, tx: dict[str, str]) -> None:
    frame = scenario_table(data, scenario, language)
    st.subheader(tx["state_title"])
    st.caption(tx["map_caption"])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(tx["municipalities"], len(frame))
    c2.metric(tx["configurations"], len(data.scenario_names))
    c3.metric(tx["highest_score"], fmt(frame["selected_score"].max(), language))
    c4.metric(tx["minimum_correlation"], fmt(data.agreement["rank_correlation"].min(), language))

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
                "profile_label": True,
                "latitude": False,
                "longitude": False,
            },
            color_continuous_scale="YlOrRd",
            size_max=22,
            zoom=4.2,
            height=620,
            labels={
                "selected_rank": tx["rank"],
                "selected_score": tx["score"],
                "profile_label": tx["stability"],
            },
        )
        fig.update_layout(map_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown(f"##### {tx['rank_title']}")
        display = frame[["selected_rank", "municipality", "selected_score", "profile_label"]]
        display = display.rename(
            columns={
                "selected_rank": tx["rank"],
                "municipality": tx["municipality"],
                "selected_score": tx["score"],
                "profile_label": tx["stability"],
            }
        )
        st.dataframe(display, hide_index=True, use_container_width=True, height=500)
        st.download_button(
            tx["download"],
            display.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"capacity_priority_{language}_{scenario}.csv",
            mime="text/csv",
            use_container_width=True,
        )


def municipal_profile_tab(data, scenario: str, language: str, tx: dict[str, str]) -> None:
    st.subheader(tx["profile_title"])
    names = sorted(data.profiles["municipality"].tolist())
    municipality = st.selectbox(tx["municipality"], names, key="profile_municipality")
    row = scenario_table(data, scenario, language).set_index("municipality").loc[municipality]
    explanation = data.explanations.set_index("municipality").loc[municipality]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(tx["selected_rank"], int(row["selected_rank"]))
    c2.metric(tx["selected_score"], fmt(row["selected_score"], language))
    c3.metric(
        tx["best_worst"], f"{int(row['best_priority_rank'])}–{int(row['worst_priority_rank'])}"
    )
    c4.metric(tx["top_quartile"], f"{100 * row['top_quartile_frequency']:.1f}%")

    left, right = st.columns(2)
    with left:
        contributions = pd.DataFrame(
            {
                tx["dimension"]: [
                    tx["institutional"],
                    tx["service_network"],
                    tx["transport_barrier"],
                ],
                tx["mean_contribution"]: [
                    explanation["mean_institutional_contribution"],
                    explanation["mean_service_network_contribution"],
                    explanation["mean_transport_barrier_contribution"],
                ],
            }
        )
        fig = px.bar(
            contributions,
            x=tx["mean_contribution"],
            y=tx["dimension"],
            orientation="h",
            color=tx["dimension"],
            text_auto=".3f",
            title=tx["contribution_title"],
        )
        fig.update_layout(showlegend=False, height=360)
        st.plotly_chart(fig, use_container_width=True)

    with right:
        rows = []
        indexed = data.scenarios.set_index("municipality")
        for name in data.scenario_names:
            transport, weight = split_scenario(name)
            rows.append(
                {
                    tx["configuration"]: scenario_label(name, language),
                    tx["macro_weight"]: WEIGHT_LABELS[language].get(weight, weight),
                    tx["rank"]: int(indexed.loc[municipality, f"{name}__rank"]),
                    "transport": transport,
                }
            )
        ranks = pd.DataFrame(rows).sort_values(tx["rank"])
        fig = px.scatter(
            ranks,
            x=tx["configuration"],
            y=tx["rank"],
            color=tx["macro_weight"],
            title=tx["rank_48"],
            hover_data=[tx["configuration"]],
        )
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(showticklabels=False, title=None)
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)

    profile = PROFILE_LABELS[language].get(
        row["priority_stability_profile"], row["priority_stability_profile"]
    )
    st.info(f"**{tx['stability_profile']}: {profile}.** {tx['stability_note']}")


def comparison_tab(data, scenario: str, language: str, tx: dict[str, str]) -> None:
    st.subheader(tx["compare_title"])
    names = sorted(data.profiles["municipality"].tolist())
    chosen = st.multiselect(tx["choose_municipalities"], names, default=names[:2], max_selections=5)
    if len(chosen) < 2:
        st.warning(tx["choose_warning"])
        return
    compare = scenario_table(data, scenario, language)
    compare = compare[compare["municipality"].isin(chosen)].copy()
    long = compare.melt(
        id_vars="municipality",
        value_vars=["institutional_deficit", "service_network_deficit", "selected_score"],
        var_name=tx["indicator"],
        value_name=tx["value"],
    )
    labels = {
        "institutional_deficit": tx["institutional_deficit"],
        "service_network_deficit": tx["service_deficit"],
        "selected_score": tx["configuration_priority"],
    }
    long[tx["indicator"]] = long[tx["indicator"]].map(labels)
    fig = px.bar(
        long,
        x=tx["indicator"],
        y=tx["value"],
        color="municipality",
        barmode="group",
        range_y=[0, 1],
        labels={"municipality": tx["municipality"]},
        title=tx["comparison_chart"],
    )
    st.plotly_chart(fig, use_container_width=True)
    columns = {
        "municipality": tx["municipality"],
        "selected_rank": tx["rank"],
        "selected_score": tx["score"],
        "best_priority_rank": tx["best_rank"],
        "worst_priority_rank": tx["worst_rank"],
        "top_quartile_frequency": tx["top_quartile"],
        "profile_label": tx["stability"],
    }
    st.dataframe(
        compare[list(columns)].rename(columns=columns), hide_index=True, use_container_width=True
    )


def methodology_tab(data, language: str, tx: dict[str, str]) -> None:
    st.subheader(tx["method_title"])
    if language == "en":
        st.markdown(
            """
            This dashboard is a **read-only visualization layer**. Scores are produced in advance by
            the audited pipeline and are not recalculated here. All 144 municipalities receive the
            same methodological treatment.

            - **Target:** relative priority for strengthening municipal capacity under multimodal access constraints.
            - **Dimensions:** institutional deficit, service-network deficit, and transport barrier.
            - **Robustness:** 12 multimodal scenarios × 4 macro-weight configurations = 48 configurations.
            - **Normalization:** within-sample percentile rank with average treatment of ties.
            - **Deliberate exclusion:** police records do not enter the active framework.
            - **Population:** 2022 Demographic Census, released and processed in 2023.

            Results support decision-making; they do not estimate violence, underreporting, service
            quality, real travel time, or automatic funding decisions.
            """
        )
    else:
        st.markdown(
            """
            Este dashboard é uma **camada de visualização somente leitura**. Os escores são produzidos
            previamente pelo pipeline auditado e não são recalculados aqui. Todos os 144 municípios
            recebem o mesmo tratamento metodológico.

            - **Objeto:** prioridade relativa para fortalecimento da capacidade municipal sob restrições de acesso multimodal.
            - **Dimensões:** déficit institucional, déficit da rede de serviços e barreira de transporte.
            - **Robustez:** 12 cenários multimodais × 4 configurações de pesos macro = 48 configurações.
            - **Normalização:** posição percentílica dentro da amostra, com média para empates.
            - **Exclusão deliberada:** registros policiais não integram o framework atual.
            - **População:** Censo Demográfico 2022, publicado e processado em 2023.

            Os resultados apoiam decisões; não estimam violência, subnotificação, qualidade do serviço,
            tempo real de viagem ou decisões automáticas de financiamento.
            """
        )
    st.markdown(f"##### {tx['agreement_title']}")
    agreement = data.agreement.copy()
    agreement[tx["configuration"]] = agreement["scenario"].map(
        lambda value: scenario_label(value, language)
    )
    columns = {
        "rank_correlation": tx["spearman"],
        "top_k_overlap_fraction": tx["top10_overlap"],
        "mean_absolute_rank_shift": tx["mean_shift"],
        "maximum_absolute_rank_shift": tx["max_shift"],
    }
    view = agreement[[tx["configuration"], *columns]].rename(columns=columns)
    st.dataframe(view, hide_index=True, use_container_width=True)


def explain_transport(transport: str, tx: dict[str, str]) -> str:
    mode, role = transport.split("__")
    mode_key = {
        "equal_modes": "mode_equal",
        "road_emphasis": "mode_road",
        "water_emphasis": "mode_water",
        "air_emphasis": "mode_air",
    }[mode]
    role_key = {
        "equal_roles": "role_equal",
        "availability_emphasis": "role_availability",
        "proximity_emphasis": "role_proximity",
    }[role]
    return f"{tx[mode_key]}; {tx[role_key]}."


language_name = st.radio(
    "Language / Idioma",
    ["English", "Português"],
    horizontal=True,
    label_visibility="collapsed",
)
language = "en" if language_name == "English" else "pt"
tx = TEXT[language]

try:
    data = get_data()
except (FileNotFoundError, KeyError, ValueError) as exc:
    st.error(f"{tx['validation_error']}: {exc}")
    st.stop()

st.title(tx["title"])
st.caption(tx["caption"])
framework_dimensions(tx)
# The two selectors map only to precomputed, audited scenario columns.
reference_transport, reference_weight = split_scenario(REFERENCE_SCENARIO)
transport_options = tuple(sorted({split_scenario(name)[0] for name in data.scenario_names}))
selector_left, selector_right = st.columns(2)
with selector_left:
    transport = st.selectbox(
        tx["transport_scenario"],
        transport_options,
        index=transport_options.index(reference_transport),
        format_func=lambda name: transport_label(name, language),
    )
with selector_right:
    macro_weight = st.selectbox(
        tx["macro_weights_selector"],
        MACRO_WEIGHT_ORDER,
        index=MACRO_WEIGHT_ORDER.index(reference_weight),
        format_func=lambda name: weight_label(name, language),
    )
scenario = compose_scenario(transport, macro_weight)
if scenario not in data.scenario_names:
    st.error(f"{tx['validation_error']}: {scenario}")
    st.stop()
institutional_weight, service_weight, transport_weight = MACRO_WEIGHTS[macro_weight]
st.info(
    f"**{tx['selected_configuration']}:** {scenario_label(scenario, language)}  \n"
    f"**{tx['transport_interpretation']}:** {explain_transport(transport, tx)}  \n"
    f"**{tx['macro_weights_detail']}:** {tx['institutional_weight']} "
    f"{pct(institutional_weight, language)} · {tx['service_weight']} "
    f"{pct(service_weight, language)} · {tx['transport_weight']} "
    f"{pct(transport_weight, language)}"
)

tab_state, tab_profile, tab_compare, tab_method = st.tabs(
    [tx["state_tab"], tx["profile_tab"], tx["compare_tab"], tx["method_tab"]]
)
with tab_state:
    statewide_tab(data, scenario, language, tx)
with tab_profile:
    municipal_profile_tab(data, scenario, language, tx)
with tab_compare:
    comparison_tab(data, scenario, language, tx)
with tab_method:
    methodology_tab(data, language, tx)

st.divider()
st.caption(tx["footer"])
