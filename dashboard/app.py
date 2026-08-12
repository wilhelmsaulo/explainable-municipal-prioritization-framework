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
        "page_title": "Response Capacity to Violence Against Women · Pará",
        "title": "Municipal prioritization of response capacity to violence against women",
        "caption": "Pará · 144 municipalities · 48 precomputed configurations · read-only visualization",
        "language": "Language",
        "navigation": "Navigation",
        "analysis_settings": "Analysis configuration",
        "overview_page": "Overview",
        "robustness_page": "Stability analysis",
        "data_method_page": "Data and methodology",
        "about_page": "About the project",
        "configuration": "Analysis configuration",
        "transport_scenario": "Transport submodel scenario",
        "macro_weights_selector": "Macro-dimension weights",
        "framework_dimensions": "Framework dimensions",
        "always_included": "Every score combines institutional capacity, the service network, and multimodal accessibility. The accessibility selector changes only that dimension; it does not remove or replace the others.",
        "institutional_card": "1 · Institutional deficit",
        "institutional_card_body": "Municipal institutional capacity for policies addressing violence against women.",
        "institutional_sources": "Source: MUNIC 2023",
        "service_card": "2 · Service-network deficit",
        "service_card_body": "Health services and professionals, specialized social assistance, justice access, and the specialized protection network.",
        "service_sources": "Sources: CNES, MDS/SNAS, TJPA, and Ligue 180",
        "transport_card": "3 · Transport barrier",
        "transport_card_body": "Road, waterway, and air access represented through 12 predeclared multimodal scenarios.",
        "transport_sources": "Sources: MapBiomas, ANTAQ, and DECEA/ICA",
        "context_note": "Female population from the 2022 Demographic Census supports contextual analyses and denominators. Police records from 2022–2025 are used only for contextual and sensitivity analyses; neither source is a criterion in the primary score.",
        "selected_configuration": "Selected configuration",
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
        "map_caption": "The map presents precomputed results and does not alter any calculation.",
        "map_source": "Municipal boundaries: IBGE Municipal Digital Mesh 2022 (SIRGAS 2000), simplified only for web visualization.",
        "map_layer": "Map layer",
        "boundary_layer": "Municipal boundaries",
        "seat_layer": "Municipal seats",
        "map_metric": "Map metric",
        "priority_score": "Priority score",
        "priority_rank": "Priority rank",
        "top_quartile_map": "Top-quartile frequency",
        "municipalities": "Municipalities",
        "configurations": "Analysis configurations",
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
        "stability_note": "This label summarizes stability across configurations; it is not an automatic allocation decision.",
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
        "robustness_title": "Stability analysis across 48 configurations",
        "robustness_caption": "Sensitivity summaries compare each predeclared configuration with the reference configuration.",
        "median_correlation": "Median rank correlation",
        "minimum_top10": "Minimum top-10 overlap",
        "maximum_shift": "Maximum rank shift",
        "agreement_chart": "Rank agreement and top-10 overlap",
        "indicator_dictionary": "Active indicator dictionary",
        "indicator_dictionary_note": "These seven indicators are the non-transport inputs used by the active framework.",
        "download_dictionary": "Download indicator dictionary (CSV)",
        "about_title": "About the project",
        "about_body": "This dashboard presents precomputed results from the multicriteria model for municipal prioritization of response capacity to violence against women in all 144 municipalities of Pará, Brazil.",
        "live_version": "Live development version",
        "research_boundary": "Research boundary",
        "research_boundary_body": "The model prioritizes the strengthening of municipal and intersectoral response capacity to violence against women. It does not estimate violence incidence, underreporting, individual risk, or automatic funding decisions.",
        "spearman": "Spearman correlation",
        "top10_overlap": "Top-10 overlap",
        "mean_shift": "Mean absolute rank shift",
        "max_shift": "Maximum absolute rank shift",
        "validation_error": "Result validation failed",
        "footer": "Municipal prioritization of response capacity to violence against women · precomputed results · dashboard parameters cannot be changed.",
    },
    "pt": {
        "page_title": "Capacidade de resposta à violência contra a mulher · Pará",
        "title": "Priorização municipal da capacidade de resposta à violência contra a mulher",
        "caption": "Pará · 144 municípios · 48 configurações pré-calculadas · visualização somente leitura",
        "language": "Idioma",
        "navigation": "Navegação",
        "analysis_settings": "Configuração da análise",
        "overview_page": "Visão geral",
        "robustness_page": "Análise de estabilidade",
        "data_method_page": "Dados e metodologia",
        "about_page": "Sobre o projeto",
        "configuration": "Configuração da análise",
        "transport_scenario": "Cenário do submodelo de transporte",
        "macro_weights_selector": "Pesos das macrodimensões",
        "framework_dimensions": "Dimensões do framework",
        "always_included": "Todo escore combina capacidade institucional, rede de serviços e acessibilidade multimodal. O seletor de acessibilidade modifica apenas essa dimensão; ele não remove nem substitui as demais.",
        "institutional_card": "1 · Déficit institucional",
        "institutional_card_body": "Capacidade institucional municipal para políticas de enfrentamento à violência contra a mulher.",
        "institutional_sources": "Fonte: MUNIC 2023",
        "service_card": "2 · Déficit da rede de serviços",
        "service_card_body": "Serviços e profissionais de saúde, assistência social especializada, acesso à justiça e rede especializada de proteção.",
        "service_sources": "Fontes: CNES, MDS/SNAS, TJPA e Ligue 180",
        "transport_card": "3 · Barreira de transporte",
        "transport_card_body": "Acesso rodoviário, hidroviário e aéreo representado por 12 cenários multimodais previamente declarados.",
        "transport_sources": "Fontes: MapBiomas, ANTAQ e DECEA/ICA",
        "context_note": "A população feminina do Censo 2022 apoia análises contextuais e denominadores. Os registros policiais de 2022–2025 são usados somente em análises contextuais e de sensibilidade; nenhuma dessas fontes integra o escore principal.",
        "selected_configuration": "Configuração selecionada",
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
        "map_caption": "O mapa apresenta resultados pré-calculados e não altera nenhum cálculo.",
        "map_source": "Limites municipais: Malha Municipal Digital 2022 do IBGE (SIRGAS 2000), simplificada apenas para visualização web.",
        "map_layer": "Camada do mapa",
        "boundary_layer": "Limites municipais",
        "seat_layer": "Sedes municipais",
        "map_metric": "Métrica do mapa",
        "priority_score": "Escore de prioridade",
        "priority_rank": "Posição no ranking",
        "top_quartile_map": "Frequência no quartil superior",
        "municipalities": "Municípios",
        "configurations": "Configurações",
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
        "stability_note": "Este rótulo resume a estabilidade entre configurações; não constitui decisão automática de alocação.",
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
        "robustness_title": "Análise de estabilidade nas 48 configurações",
        "robustness_caption": "Os resumos de sensibilidade comparam cada configuração previamente declarada com a configuração de referência.",
        "median_correlation": "Correlação mediana entre rankings",
        "minimum_top10": "Menor sobreposição do top 10",
        "maximum_shift": "Maior mudança de posição",
        "agreement_chart": "Concordância dos rankings e sobreposição do top 10",
        "indicator_dictionary": "Dicionário dos indicadores ativos",
        "indicator_dictionary_note": "Estes sete indicadores são as entradas não relacionadas ao transporte utilizadas pelo framework ativo.",
        "download_dictionary": "Baixar dicionário dos indicadores (CSV)",
        "about_title": "Sobre o projeto",
        "about_body": "Este dashboard apresenta resultados pré-calculados do modelo multicritério de priorização municipal da capacidade de resposta à violência contra a mulher nos 144 municípios do Pará.",
        "live_version": "Versão de desenvolvimento ativa",
        "research_boundary": "Limite da pesquisa",
        "research_boundary_body": "O modelo prioriza o fortalecimento da capacidade municipal e intersetorial de resposta à violência contra a mulher. Ele não estima incidência de violência, subnotificação, risco individual ou decisões automáticas de financiamento.",
        "spearman": "Correlação de Spearman",
        "top10_overlap": "Sobreposição top 10",
        "mean_shift": "Mudança média absoluta de posição",
        "max_shift": "Mudança máxima absoluta de posição",
        "validation_error": "Falha na validação dos resultados",
        "footer": "Priorização municipal da capacidade de resposta à violência contra a mulher · resultados pré-calculados · os parâmetros não podem ser alterados.",
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

    control_left, control_right = st.columns(2)
    with control_left:
        map_layer = st.radio(
            tx["map_layer"],
            ["boundaries", "seats"],
            horizontal=True,
            format_func=lambda value: {
                "boundaries": tx["boundary_layer"],
                "seats": tx["seat_layer"],
            }[value],
        )
    metric_labels = {
        "score": tx["priority_score"],
        "rank": tx["priority_rank"],
        "top_quartile": tx["top_quartile_map"],
    }
    with control_right:
        map_metric = st.selectbox(
            tx["map_metric"],
            tuple(metric_labels),
            format_func=metric_labels.get,
        )
    metric_columns = {
        "score": "selected_score",
        "rank": "selected_rank",
        "top_quartile": "top_quartile_frequency",
    }
    metric_column = metric_columns[map_metric]
    color_scale = "YlOrRd_r" if map_metric == "rank" else "YlOrRd"

    left, right = st.columns([1.45, 1])
    with left:
        hover_data = {
            "selected_rank": True,
            "selected_score": ":.3f",
            "top_quartile_frequency": ":.1%",
            "profile_label": True,
        }
        labels = {
            "selected_rank": tx["rank"],
            "selected_score": tx["score"],
            "top_quartile_frequency": tx["top_quartile_map"],
            "profile_label": tx["stability"],
        }
        if map_layer == "boundaries":
            fig = px.choropleth_map(
                frame,
                geojson=data.boundaries,
                locations="municipality_code",
                featureidkey="properties.CD_MUN",
                color=metric_column,
                hover_name="municipality",
                hover_data=hover_data,
                color_continuous_scale=color_scale,
                center={"lat": -3.8, "lon": -52.3},
                zoom=4.2,
                opacity=0.78,
                height=620,
                labels=labels,
            )
        else:
            fig = px.scatter_map(
                frame,
                lat="latitude",
                lon="longitude",
                color=metric_column,
                hover_name="municipality",
                hover_data={**hover_data, "latitude": False, "longitude": False},
                color_continuous_scale=color_scale,
                zoom=4.2,
                height=620,
                labels=labels,
            )
            fig.update_traces(marker={"size": 11})
        fig.update_layout(map_style="carto-positron", margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(tx["map_source"])

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
            - **Stability analysis:** 12 multimodal scenarios × 4 macro-weight configurations = 48 configurations.
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
            - **Análise de estabilidade:** 12 cenários multimodais × 4 configurações de pesos macro = 48 configurações.
            - **Normalização:** posição percentílica dentro da amostra, com média para empates.
            - **Exclusão deliberada:** registros policiais não integram o framework atual.
            - **População:** Censo Demográfico 2022, publicado e processado em 2023.

            Os resultados apoiam decisões; não estimam violência, subnotificação, qualidade do serviço,
            tempo real de viagem ou decisões automáticas de financiamento.
            """
        )
    st.markdown(f"##### {tx['indicator_dictionary']}")
    st.caption(tx["indicator_dictionary_note"])
    profile = data.indicator_profile.copy()
    st.dataframe(profile, hide_index=True, use_container_width=True)
    st.download_button(
        tx["download_dictionary"],
        profile.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"active_indicator_dictionary_{language}.csv",
        mime="text/csv",
    )


def robustness_page(data, language: str, tx: dict[str, str]) -> None:
    st.subheader(tx["robustness_title"])
    st.caption(tx["robustness_caption"])
    agreement = data.agreement.copy()
    agreement[tx["configuration"]] = agreement["scenario"].map(
        lambda value: scenario_label(value, language)
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(tx["minimum_correlation"], fmt(agreement["rank_correlation"].min(), language))
    c2.metric(tx["median_correlation"], fmt(agreement["rank_correlation"].median(), language))
    c3.metric(tx["minimum_top10"], fmt(agreement["top_k_overlap_fraction"].min(), language))
    c4.metric(tx["maximum_shift"], int(agreement["maximum_absolute_rank_shift"].max()))
    figure = px.scatter(
        agreement,
        x="rank_correlation",
        y="top_k_overlap_fraction",
        color="macro_weight_scenario",
        hover_name=tx["configuration"],
        labels={
            "rank_correlation": tx["spearman"],
            "top_k_overlap_fraction": tx["top10_overlap"],
            "macro_weight_scenario": tx["macro_weight"],
        },
        title=tx["agreement_chart"],
    )
    st.plotly_chart(figure, use_container_width=True)
    st.markdown(f"##### {tx['agreement_title']}")
    columns = {
        "rank_correlation": tx["spearman"],
        "top_k_overlap_fraction": tx["top10_overlap"],
        "mean_absolute_rank_shift": tx["mean_shift"],
        "maximum_absolute_rank_shift": tx["max_shift"],
    }
    view = agreement[[tx["configuration"], *columns]].rename(columns=columns)
    st.dataframe(view, hide_index=True, use_container_width=True)


def about_page(tx: dict[str, str]) -> None:
    st.subheader(tx["about_title"])
    st.write(tx["about_body"])
    st.markdown(
        "**GitHub:** [Municipal Response Capacity Prioritization Model]"
        "(https://github.com/wilhelmsaulo/explainable-municipal-prioritization-framework)"
    )
    st.markdown(
        "**Dashboard:** [Streamlit Community Cloud]"
        "(https://explainable-municipal-prioritization-framework-zyur6g28v6z5uba.streamlit.app/)"
    )
    st.markdown(f"#### {tx['research_boundary']}")
    st.write(tx["research_boundary_body"])


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


with st.sidebar:
    language = st.radio(
        "Language / Idioma",
        ["en", "pt"],
        horizontal=True,
        format_func=lambda value: "English" if value == "en" else "Português",
    )
tx = TEXT[language]

try:
    data = get_data()
except (FileNotFoundError, KeyError, ValueError) as exc:
    st.error(f"{tx['validation_error']}: {exc}")
    st.stop()

reference_transport, reference_weight = split_scenario(REFERENCE_SCENARIO)
transport_options = tuple(sorted({split_scenario(name)[0] for name in data.scenario_names}))
page_labels = {
    "overview": tx["overview_page"],
    "profile": tx["profile_tab"],
    "comparison": tx["compare_tab"],
    "robustness": tx["robustness_page"],
    "data_method": tx["data_method_page"],
    "about": tx["about_page"],
}
with st.sidebar:
    st.divider()
    st.subheader(tx["navigation"])
    page = st.radio(
        tx["navigation"],
        tuple(page_labels),
        format_func=page_labels.get,
        label_visibility="collapsed",
    )
    st.divider()
    with st.expander(tx["analysis_settings"], expanded=True):
        transport = st.selectbox(
            tx["transport_scenario"],
            transport_options,
            index=transport_options.index(reference_transport),
            format_func=lambda name: transport_label(name, language),
        )
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
st.title(tx["title"])
st.caption(tx["caption"])

if page in {"overview", "profile", "comparison"}:
    st.info(
        f"**{tx['selected_configuration']}:** {scenario_label(scenario, language)}  \n"
        f"**{tx['transport_interpretation']}:** {explain_transport(transport, tx)}  \n"
        f"**{tx['macro_weights_detail']}:** {tx['institutional_weight']} "
        f"{pct(institutional_weight, language)} · {tx['service_weight']} "
        f"{pct(service_weight, language)} · {tx['transport_weight']} "
        f"{pct(transport_weight, language)}"
    )

if page == "overview":
    framework_dimensions(tx)
    statewide_tab(data, scenario, language, tx)
elif page == "profile":
    municipal_profile_tab(data, scenario, language, tx)
elif page == "comparison":
    comparison_tab(data, scenario, language, tx)
elif page == "robustness":
    robustness_page(data, language, tx)
elif page == "data_method":
    methodology_tab(data, language, tx)
else:
    about_page(tx)

st.divider()
st.caption(tx["footer"])
