"""Etapas e gates do assistente. O avanço é uma função pura do estado já gravado."""

from __future__ import annotations

from typing import Any

from .optics import (
    CELL_NAMES,
    MIN_ACCEPTED,
    PATTERN,
    REPROJECTION_LIMIT_PX,
    VALIDATION_PLANES_MM,
    missing_cells,
    suggestion_for,
)

STAGES = (
    "fix_hardware",
    "capture_intrinsic",
    "review_reprojection",
    "confirm_undistort",
    "teach_frame",
    "solve_extrinsic",
    "confirm_direction",
    "validate_planes",
    "affine_mold",
    "analyze_residuals",
)

BOARD_STAGES = frozenset({"capture_intrinsic", "solve_extrinsic", "validate_planes", "confirm_undistort"})

STAGE_GUIDE: dict[str, dict[str, str]] = {
    "fix_hardware": {
        "title": "1. Fixar o hardware",
        "what": "Coloque o tabuleiro à frente da lente. Gire o anel até a nitidez estabilizar no máximo e só então trave o foco, a câmera e a resolução.",
        "why": "K e a distorção só valem para esse foco e para esse raster. Se o anel mudar, a campanha recomeça.",
        "gate": "Nitidez estável no máximo, foco travado, os outros itens do checklist marcados e o lado do quadrado maior que zero.",
    },
    "capture_intrinsic": {
        "title": "2. Capturar a intrínseca",
        "what": "Mostre o tabuleiro rígido em várias posições. Aceite só imagens com todos os cantos internos nítidos.",
        "why": "A lente precisa ser excitada no centro, nos cantos, nas bordas, com inclinação e com distância diferente.",
        "gate": f"Pelo menos {MIN_ACCEPTED} imagens aceitas, todos os cantos internos em cada uma, e as nove regiões do campo cobertas.",
    },
    "review_reprojection": {
        "title": "3. Revisar a reprojeção",
        "what": "Calcule K e a distorção. Olhe o erro de cada imagem. Exclua a que passar do limite e calcule de novo.",
        "why": "O erro de reprojeção é em pixels. Ele mede a câmera, não o robô. Uma imagem ruim puxa K inteiro.",
        "gate": f"Solução calculada com as imagens ainda aceitas, nenhuma acima de {REPROJECTION_LIMIT_PX:.1f} px, e a revisão confirmada.",
    },
    "confirm_undistort": {
        "title": "4. Ver a imagem corrigida",
        "what": "Compare o frame antes e depois. A origem do tabuleiro continua marcada em vermelho nas capturas.",
        "why": "Daqui para a frente o ponto do molde entra na afim já corrigido. O RF-DETR continua vendo o frame bruto.",
        "gate": "Confirme que a cadeia seguinte usa a imagem corrigida.",
    },
    "teach_frame": {
        "title": "5. Ensinar origem e eixos",
        "what": "Congele a imagem com o tabuleiro parado e a origem vermelha visível. Depois encoste o TCP na origem, em +X e em +Y e grave cada pose. O robô cobre o tabuleiro; a imagem congelada continua mostrando o ponto.",
        "why": "solvePnP enxerga o tabuleiro na câmera. Sem estes três toques, essa pose não está no referencial do robô.",
        "gate": "Três poses gravadas e eixos que não sejam quase a mesma reta.",
    },
    "solve_extrinsic": {
        "title": "6. Calibrar a extrínseca",
        "what": "Sem mover o tabuleiro ensinado, capture uma imagem e calcule solvePnP. A tela mostra os dois sentidos da transformação.",
        "why": "O sentido trocado inverte sinais e o erro cresce longe do centro.",
        "gate": "Uma imagem nova desta etapa, com solução R e t guardada para essa imagem.",
    },
    "confirm_direction": {
        "title": "7. Conferir o sentido",
        "what": "Congele a imagem com a origem vermelha visível. Encoste o TCP no canto interno a um quadrado da origem, no eixo X, e compare com as duas previsões.",
        "why": "A previsão certa fica perto do TCP. A invertida cai do outro lado da origem.",
        "gate": "O sentido tabuleiro → câmera precisa ser o de menor erro. O sentido invertido não avança.",
    },
    "validate_planes": {
        "title": "8. Validar os três planos",
        "what": "Escolha 0, 200 ou 400 mm, na ordem que for mais fácil. Aceite uma imagem nova do tabuleiro em cada altura. Não reuse as fotos do ajuste.",
        "why": "Medir com as mesmas fotos do cálculo deixa o erro otimista.",
        "gate": "Uma imagem nova em 0, 200 e 400 mm, em qualquer ordem, com MAE, RMSE e máximo em milímetros.",
    },
    "affine_mold": {
        "title": "9. Afim com o molde",
        "what": "Retire o tabuleiro. Escolha uma coleta de afim já feita ou abra uma nova. O alvo passa a ser o molde, visto pelo RF-DETR.",
        "why": "A afim agora só absorve o resíduo entre o centroide corrigido e o centro da ferramenta.",
        "gate": "A sessão do molde está ligada a este perfil e ao menos um plano já tem modelo.",
    },
    "analyze_residuals": {
        "title": "10. Analisar os resíduos",
        "what": "Leia o resumo: reprojeção da lente, erro do sentido, validação dos planos e RMS da afim. Finalize a campanha para a câmera voltar a procurar o molde.",
        "why": "O guia separa lente, pose da câmera, TCP e coleta. Cada padrão pede uma ação diferente.",
        "gate": "Confira os números e finalize a campanha para voltar à busca do molde.",
    },
}


def next_stage(stage: str) -> str:
    index = STAGES.index(stage)
    if index + 1 >= len(STAGES):
        raise ValueError("A campanha já está na última etapa")
    return STAGES[index + 1]


def _accepted(captures: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    return [item for item in captures if item["stage"] == stage and item["decision"] == "accepted"]


def _filled_cells(captures: list[dict[str, Any]]) -> set[tuple[int, int]]:
    filled: set[tuple[int, int]] = set()
    for item in captures:
        cell = item.get("cell")
        if item["decision"] == "accepted" and cell and len(cell) == 2:
            filled.add((int(cell[0]), int(cell[1])))
    return filled


def gate_for(snapshot: dict[str, Any]) -> dict[str, Any]:
    stage = snapshot["stage"]
    captures: list[dict[str, Any]] = snapshot.get("captures") or []
    if stage == "fix_hardware" and snapshot.get("focus_drift"):
        return _blocked("O foco caiu em relação ao valor travado. Recomece a campanha.")
    if stage == "fix_hardware":
        checks = snapshot.get("checks") or {}
        required = ("camera_fixed", "lens_focus_locked", "production_resolution", "single_stapi_client")
        if not snapshot.get("focus_lock"):
            return _blocked("Mostre o tabuleiro e estabilize a nitidez no máximo antes de travar o foco.")
        if not all(checks.get(key) for key in required):
            return _blocked("Marque os quatro itens do checklist antes de avançar.")
        if float(snapshot.get("square_size_mm") or 0) <= 0:
            return _blocked("Informe o lado do quadrado medido, em milímetros.")
        return _open("Foco travado no máximo e hardware fixado.")
    if stage == "capture_intrinsic":
        accepted = _accepted(captures, "capture_intrinsic")
        if len(accepted) < MIN_ACCEPTED:
            return _blocked(f"Faltam {MIN_ACCEPTED - len(accepted)} imagens aceitas.")
        pattern = snapshot.get("pattern") or PATTERN
        expected = int(pattern[0]) * int(pattern[1])
        if any(int(item.get("corner_count") or 0) != expected for item in accepted):
            return _blocked(f"Toda imagem aceita precisa ter {expected} cantos.")
        missing = missing_cells(_filled_cells(accepted))
        if missing:
            return _blocked(f"Ainda falta cobertura: {missing[0]}.")
        return _open("Cobertura e quantidade de imagens suficientes.")
    if stage == "review_reprojection":
        accepted = _accepted(captures, "capture_intrinsic")
        intrinsic = snapshot.get("intrinsic")
        if not intrinsic:
            return _blocked("Calcule a intrínseca antes de avançar.")
        accepted_ids = sorted(item["id"] for item in accepted)
        if sorted(intrinsic.get("capture_ids") or []) != accepted_ids:
            return _blocked("O conjunto mudou. Calcule a intrínseca de novo.")
        suspects = [
            item for item in accepted
            if item.get("reprojection_px") is None or float(item["reprojection_px"]) > REPROJECTION_LIMIT_PX
        ]
        if suspects:
            return _blocked("Exclua as imagens acima do limite e calcule de novo.")
        if not snapshot.get("reprojection_reviewed"):
            return _blocked("Confirme que a reprojeção foi inspecionada imagem a imagem.")
        return _open("Reprojeção revisada.")
    if stage == "confirm_undistort":
        if not snapshot.get("undistort_confirmed"):
            return _blocked("Confirme o uso da imagem corrigida.")
        return _open("A cadeia seguinte usa a imagem corrigida.")
    if stage == "teach_frame":
        points = snapshot.get("frame_points") or {}
        if not all(points.get(role) for role in ("origin", "plus_x", "plus_y")):
            return _blocked("Grave origem, +X e +Y.")
        if not snapshot.get("board_frame"):
            return _blocked("Os eixos não formam um referencial. Grave os três pontos de novo.")
        return _open("Referencial do tabuleiro gravado.")
    if stage == "solve_extrinsic":
        accepted = _accepted(captures, "solve_extrinsic")
        extrinsic = snapshot.get("extrinsic")
        if len(accepted) != 1 or not extrinsic:
            return _blocked("Capture uma imagem desta pose e calcule solvePnP.")
        if extrinsic.get("capture_id") != accepted[0]["id"]:
            return _blocked("A solução não corresponde à imagem aceita. Calcule de novo.")
        return _open("Extrínseca calculada para a imagem desta etapa.")
    if stage == "confirm_direction":
        check = snapshot.get("direction_check") or {}
        if "error_correct_mm" not in check:
            return _blocked("Grave a pose do TCP no canto de conferência.")
        if float(check["error_correct_mm"]) > float(check["error_inverted_mm"]):
            return _blocked("O sentido invertido está mais perto do TCP. Reensine os eixos.")
        if snapshot.get("direction") != "object_to_camera":
            return _blocked("Confirme o sentido tabuleiro → câmera. O sentido invertido não avança.")
        return _open("Sentido conferido.")
    if stage == "validate_planes":
        used = {item["id"] for item in captures if item["stage"] in {"capture_intrinsic", "solve_extrinsic"}}
        accepted = [
            item for item in _accepted(captures, "validate_planes")
            if item["id"] not in used and item.get("metrics")
        ]
        missing = [
            plane for plane in VALIDATION_PLANES_MM
            if not any(_matches_plane(item.get("plan_z"), plane) for item in accepted)
        ]
        if missing:
            listed = ", ".join(f"{plane:.0f} mm" for plane in missing)
            return _blocked(f"Escolha entre {listed}. A ordem é livre.")
        return _open("0, 200 e 400 mm têm validação independente.")
    if stage == "affine_mold":
        if not snapshot.get("affine_session_id"):
            return _blocked("Abra a coleta do molde ligada a este perfil.")
        if not snapshot.get("affine_ready"):
            return _blocked("Grave pontos do molde até um plano ter modelo afim.")
        return _open("A afim residual já tem modelo.")
    if stage == "analyze_residuals":
        return _open("Confira os números e finalize a campanha para voltar à busca do molde.")
    return _blocked("Etapa desconhecida.")


def _matches_plane(stored: Any, plane: float) -> bool:
    if stored is None:
        return False
    return abs(float(stored) - float(plane)) < 1e-6


def _blocked(reason: str) -> dict[str, Any]:
    return {"passed": False, "reason": reason}


def _open(reason: str) -> dict[str, Any]:
    return {"passed": True, "reason": reason}


def coverage_view(captures: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = _accepted(captures, "capture_intrinsic")
    filled = _filled_cells(accepted)
    return {
        "filled": [list(cell) for cell in sorted(filled)],
        "missing": missing_cells(filled),
        "suggestion": suggestion_for(filled),
        "labels": {f"{col},{row}": name for (col, row), name in CELL_NAMES.items()},
    }

