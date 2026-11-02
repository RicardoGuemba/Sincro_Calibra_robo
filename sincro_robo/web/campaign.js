let campaignSignature = "";
let campaignBusy = false;
let chosenValidationPlane = null;

function campaignPost(path, body) {
  campaignBusy = true;
  const options = { method: "POST" };
  if (body !== undefined) options.body = JSON.stringify(body);
  return api(path, options)
    .then(() => {
      campaignSignature = "";
      return true;
    })
    .catch((error) => {
      toast(error.message, "error");
      return false;
    })
    .finally(async () => {
      campaignBusy = false;
      await refreshState();
    });
}

function campaignWhen(value) {
  const text = String(value || "");
  if (text.length < 16) return "";
  return `${text.slice(8, 10)}/${text.slice(5, 7)} ${text.slice(11, 16)}`;
}

async function resumeCampaign(campaignId) {
  try {
    const resumed = await api(`/api/campaigns/${campaignId}/open`, { method: "POST" });
    campaignSignature = "";
    await refreshState();
    toast(`Campanha retomada em ${resumed.copy.title}.`);
  } catch (error) {
    toast(error.message, "error");
  }
}

function campaignLabel(item) {
  const when = campaignWhen(item.created_at);
  const detail = when ? `${item.stage_title} · ${when}` : item.stage_title;
  const closed = item.status === "closed" ? " · fechada" : "";
  return `${item.name} — ${detail}${closed}`;
}

function syncCampaignButtons() {
  const select = document.getElementById("campaign-select");
  const hasChoice = Boolean(select && select.value);
  const open = document.getElementById("open-campaign");
  const remove = document.getElementById("delete-campaign");
  if (open) open.disabled = !hasChoice;
  if (remove) remove.disabled = !hasChoice;
}

function paintCampaignList(campaigns, activeId) {
  const select = document.getElementById("campaign-select");
  if (!select) return;
  const items = Array.isArray(campaigns) ? campaigns : [];
  const signature = `${activeId || ""}|${items.map((item) => `${item.id}:${item.stage}:${item.status}:${item.name}`).join("|")}`;
  if (select.dataset.signature === signature) return;
  const previousActive = select.dataset.active || "";
  const keepSelection = previousActive === (activeId || "") && items.some((item) => item.id === select.value);
  const chosen = keepSelection ? select.value : (activeId || "");
  select.replaceChildren();
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = items.length ? "Selecionar campanha…" : "Nenhuma campanha gravada";
  select.appendChild(placeholder);
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = campaignLabel(item);
    select.appendChild(option);
  });
  select.value = items.some((item) => item.id === chosen) ? chosen : "";
  select.dataset.signature = signature;
  select.dataset.active = activeId || "";
  syncCampaignButtons();
}

function campaignLiveText(campaign) {
  if (campaign.stage === "analyze_residuals") return "";
  if (campaign.frame_frozen) {
    return `Imagem congelada${campaign.detection?.found ? ` · ${campaign.detection.count} cantos` : ""}`;
  }
  return campaign.detection?.found
    ? `Tabuleiro visto · ${campaign.detection.count} cantos`
    : "Tabuleiro não detectado neste frame";
}

function summaryNumber(value, digits) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "—";
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function campaignSummary(campaign) {
  const summary = campaign.summary;
  if (!summary) return "";
  const pattern = Array.isArray(summary.pattern) ? summary.pattern : ["—", "—"];
  const tcp = Array.isArray(summary.tcp_local_mm) ? summary.tcp_local_mm.map((value) => summaryNumber(value, 0)).join(" · ") : "—";
  const validation = (summary.validation || []).map((item) => `Z ${summaryNumber(item.z, 0)} · RMSE ${summaryNumber(item.rmse, 1)} mm · máx ${summaryNumber(item.max, 1)} mm`).join("<br>") || "Sem imagem de validação";
  const affine = (summary.affine_planes || []).map((item) => item.ready
    ? `Z ${summaryNumber(item.z, 0)} · RMS ${summaryNumber(item.rms_mm, 1)} mm · máx ${summaryNumber(item.max_mm, 1)} mm · ${item.points} pontos`
    : `Z ${summaryNumber(item.z, 0)} · sem modelo`).join("<br>") || "Sem sessão de molde";
  const session = summary.affine_session_name ? escapeHtml(summary.affine_session_name) : "Sem sessão ligada";
  return `<div class="campaign-summary">
    <div><span>Reprojeção da lente</span><strong>${summaryNumber(summary.reprojection_rms_px, 3)} px</strong><small>${summary.accepted_images} imagens aceitas</small></div>
    <div><span>Sentido tabuleiro → câmera</span><strong>${summaryNumber(summary.direction_correct_mm, 1)} mm</strong><small>sentido invertido ${summaryNumber(summary.direction_inverted_mm, 1)} mm</small></div>
    <div><span>Quadrado e padrão</span><strong>${summaryNumber(summary.square_size_mm, 1)} mm</strong><small>${pattern[0]} × ${pattern[1]} cantos internos</small></div>
    <div><span>Validação dos planos</span><strong>${validation}</strong></div>
    <div><span>Afim do molde</span><strong>${affine}</strong><small>${session}</small></div>
    <div><span>TCP no referencial da ferramenta</span><strong>${tcp} mm</strong><small>X · Y</small></div>
  </div>`;
}

function renderCampaign(campaign) {
  paintCampaignList(app.state?.campaigns, campaign?.id);
  const body = document.getElementById("campaign-body");
  if (!body || campaignBusy) return;
  if (!campaign) {
    campaignSignature = "none";
    body.innerHTML = '<p class="campaign-lead">Nenhuma campanha aberta. A coleta do molde abaixo continua disponível.</p>';
    return;
  }
  const live = document.getElementById("campaign-live");
  const liveText = campaignLiveText(campaign);
  if (live) {
    live.hidden = campaign.stage === "analyze_residuals";
    live.textContent = liveText;
  }
  paintFocus(campaign);
  const signature = JSON.stringify({
    stage: campaign.stage,
    gate: campaign.gate,
    accepted: campaign.accepted_count,
    coverage: campaign.coverage,
    checks: campaign.checks,
    focusStable: campaign.focus?.stable,
    focusDrift: campaign.focus?.drift,
    focusLocked: campaign.focus?.locked_peak,
    reprojection: campaign.reprojection,
    frame: campaign.frame_points,
    frameFrozen: campaign.frame_frozen,
    direction: campaign.direction_check,
    validation: campaign.validation,
    validationPlane: campaign.validation_plan_z,
    diagnosis: campaign.diagnosis,
    summary: campaign.summary,
    affine: campaign.affine_session_id,
    sessions: (app.sessions || []).map((session) => session.id).join(","),
    sha: campaign.profile_sha256,
  });
  if (signature === campaignSignature) return;
  campaignSignature = signature;
  const rail = campaign.stages.map((stage) => `<span class="${stage.state}">${stage.title}</span>`).join("");
  const gateClass = campaign.gate.passed ? "campaign-gate open" : "campaign-gate";
  body.innerHTML = `
    <div class="campaign-rail">${rail}</div>
    <div class="campaign-copy">
      <div>
        <p><strong>O que fazer.</strong> ${campaign.copy.what}</p>
        <p><strong>Por quê.</strong> ${campaign.copy.why}</p>
      </div>
      <div class="${gateClass}"><strong>${campaign.stage === "analyze_residuals" ? "Para concluir." : "Para avançar."}</strong> ${campaign.gate.reason}</div>
    </div>
    ${campaign.stage === "analyze_residuals" ? campaignSummary(campaign) : ""}
    <div class="campaign-actions" id="campaign-actions"></div>
    <p class="campaign-live" id="campaign-live" ${campaign.stage === "analyze_residuals" ? "hidden" : ""}>${liveText}</p>
    <p class="focus-meter" id="focus-meter" ${campaign.stage === "analyze_residuals" ? "hidden" : ""}></p>
  `;
  paintFocus(campaign);
  const actions = document.getElementById("campaign-actions");
  const stage = campaign.stage;
  if (campaign.focus?.drift) {
    addButton(actions, "Recomeçar campanha", () => campaignPost("/api/campaigns/active/restart"));
    return;
  }
  if (stage === "fix_hardware") {
    const labels = [
      ["camera_fixed", "Câmera fixa no suporte"],
      ["lens_focus_locked", "Lente e foco travados como na produção"],
      ["production_resolution", "Resolução e downscale iguais aos da produção"],
      ["single_stapi_client", "Nenhum outro programa está com a câmera"],
    ];
    labels.forEach(([key, label]) => {
      const box = document.createElement("label");
      const disabled = key === "lens_focus_locked" && !campaign.focus?.stable && !campaign.checks[key];
      box.innerHTML = `<input type="checkbox" data-check="${key}" ${campaign.checks[key] ? "checked" : ""} ${disabled ? "disabled" : ""}> ${label}`;
      actions.appendChild(box);
    });
    actions.querySelectorAll("input").forEach((input) => {
      input.addEventListener("change", () => {
        const checks = { ...campaign.checks };
        actions.querySelectorAll("input").forEach((node) => {
          checks[node.dataset.check] = node.checked;
        });
        campaignPost("/api/campaigns/active/checks", checks);
      });
    });
  }
  if (stage === "capture_intrinsic") {
    actions.innerHTML = `<span>${campaign.accepted_count} aceitas · ${campaign.coverage.suggestion}</span>`;
    addButton(actions, "Aceitar imagem", () => campaignPost("/api/campaigns/active/captures", { decision: "accepted" }));
    addButton(actions, "Rejeitar", () => campaignPost("/api/campaigns/active/captures", { decision: "rejected", reason: "Imagem ruim" }), true);
  }
  if (stage === "review_reprojection") {
    addButton(actions, "Calcular K e distorção", () => campaignPost("/api/campaigns/active/intrinsic/solve"));
    addButton(actions, "Reprojeção inspecionada", () => campaignPost("/api/campaigns/active/reprojection/confirm"), true);
    const list = document.createElement("ul");
    list.className = "campaign-list";
    (campaign.reprojection.images || []).forEach((image) => {
      const item = document.createElement("li");
      const error = image.error_px === null || image.error_px === undefined ? "—" : Number(image.error_px).toFixed(3);
      item.textContent = `${image.id.slice(0, 8)} · ${error} px${image.suspect ? " · suspeita" : ""}`;
      if (image.suspect) {
        const exclude = document.createElement("button");
        exclude.className = "button button-secondary";
        exclude.textContent = "Excluir";
        exclude.addEventListener("click", () => campaignPost(`/api/campaigns/active/captures/${image.id}/exclude`));
        item.appendChild(exclude);
      }
      list.appendChild(item);
    });
    actions.appendChild(list);
  }
  if (stage === "confirm_undistort") {
    addButton(actions, "A cadeia seguinte usa a imagem corrigida", () => campaignPost("/api/campaigns/active/undistort/confirm"));
  }
  if (stage === "teach_frame") {
    if (campaign.frame_frozen) {
      addButton(actions, "Soltar imagem", () => campaignPost("/api/campaigns/active/preview/release"));
    } else {
      addButton(actions, "Congelar imagem", () => campaignPost("/api/campaigns/active/preview/freeze"));
    }
    addButton(actions, "Gravar origem", () => campaignPost("/api/campaigns/active/frame/origin"), true);
    addButton(actions, "Gravar +X", () => campaignPost("/api/campaigns/active/frame/plus_x"), true);
    addButton(actions, "Gravar +Y", () => campaignPost("/api/campaigns/active/frame/plus_y"), true);
    const note = document.createElement("span");
    note.textContent = campaign.frame_frozen
      ? "Imagem parada. Encoste o TCP nos pontos marcados e grave. O robô pode cobrir o tabuleiro."
      : "Congele só quando a origem vermelha estiver visível. A pose do robô continua ao vivo.";
    actions.appendChild(note);
  }
  if (stage === "solve_extrinsic") {
    addButton(actions, "Aceitar imagem desta pose", () => campaignPost("/api/campaigns/active/captures", { decision: "accepted" }));
    addButton(actions, "Calcular solvePnP", () => campaignPost("/api/campaigns/active/extrinsic/solve"), true);
  }
  if (stage === "confirm_direction") {
    if (campaign.frame_frozen) {
      addButton(actions, "Soltar imagem", () => campaignPost("/api/campaigns/active/preview/release"));
    } else {
      addButton(actions, "Congelar imagem", () => campaignPost("/api/campaigns/active/preview/freeze"));
    }
    addButton(actions, "Gravar TCP neste canto", () => campaignPost("/api/campaigns/active/direction/touch"), true);
    addButton(actions, "Confirmar tabuleiro → câmera", () => campaignPost("/api/campaigns/active/direction/confirm", { sense: "object_to_camera" }), true);
    const touchNote = document.createElement("span");
    touchNote.textContent = campaign.frame_frozen
      ? "Imagem parada. Encoste o TCP no canto e grave. O robô pode cobrir o tabuleiro."
      : app.config?.mode?.plc === "synthetic"
        ? "No simulador, a pose já está no canto a um quadrado da origem."
        : "Congele com a origem vermelha visível. Depois encoste o TCP no canto interno a um quadrado da origem, no eixo X.";
    actions.appendChild(touchNote);
    if (campaign.direction_check) {
      const note = document.createElement("span");
      note.textContent = `Erro do sentido certo ${Number(campaign.direction_check.error_correct_mm).toFixed(1)} mm · invertido ${Number(campaign.direction_check.error_inverted_mm).toFixed(1)} mm`;
      actions.appendChild(note);
    }
  }
  if (stage === "validate_planes") {
    const recorded = Array.isArray(campaign.validation) ? campaign.validation : [];
    const serverPlane = Number(campaign.validation_plan_z);
    if (chosenValidationPlane !== null && Math.abs(serverPlane - chosenValidationPlane) < 1) {
      chosenValidationPlane = null;
    }
    const selected = chosenValidationPlane ?? serverPlane;
    [0, 200, 400].forEach((plane) => {
      const metric = recorded.find((item) => Math.abs(Number(item.z) - plane) < 1);
      const chosen = Math.abs(selected - plane) < 1e-6;
      const label = metric
        ? `Z ${plane} · RMSE ${Number(metric.rmse).toFixed(1)} mm`
        : chosen
          ? `Z ${plane} mm · escolhida`
          : `Z ${plane} mm`;
      const button = addButton(actions, label, () => chooseValidationPlane(plane), !chosen);
      button.dataset.plane = String(plane);
    });
    addButton(actions, `Aceitar imagem em Z ${Number.isFinite(selected) ? selected : 0} mm`, () => {
      acceptValidationImage(chosenValidationPlane ?? selected);
    });
  }
  if (stage === "affine_mold") {
    const sessions = Array.isArray(app.sessions) ? app.sessions : [];
    const select = document.createElement("select");
    select.id = "affine-session-select";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Escolher coleta já feita…";
    select.appendChild(placeholder);
    sessions.forEach((session) => {
      const option = document.createElement("option");
      option.value = session.id;
      option.textContent = session.name;
      if (session.id === campaign.affine_session_id) option.selected = true;
      select.appendChild(option);
    });
    actions.appendChild(select);
    addButton(actions, "Usar esta coleta", () => {
      const id = document.getElementById("affine-session-select")?.value;
      if (!id) {
        toast("Escolha uma coleta já feita.", "error");
        return;
      }
      campaignPost("/api/campaigns/active/affine/use", { session_id: id });
    });
    addButton(actions, "Abrir coleta nova", () => campaignPost("/api/campaigns/active/affine/open"), true);
    if (campaign.affine_session_id) {
      const note = document.createElement("span");
      const label = campaign.affine_session_name || "Sessão do molde";
      note.textContent = `${label} ligada a este perfil. Use CAPTURAR PONTO para acrescentar pontos. O centroide entra corrigido.`;
      actions.appendChild(note);
    }
    if (campaign.profile_sha256) {
      const hash = document.createElement("span");
      hash.textContent = `Perfil ${campaign.profile_sha256.slice(0, 12)}`;
      actions.appendChild(hash);
    }
  }
  if (stage === "analyze_residuals") {
    addButton(actions, "Finalizar campanha", () => {
      if (!window.confirm("Finalizar a campanha? O perfil permanece gravado e a câmera volta a procurar o molde.")) return;
      campaignPost("/api/campaigns/active/finish").then((ok) => {
        if (ok) toast("Campanha finalizada. A câmera voltou a procurar o molde.");
      });
    });
    if (campaign.diagnosis) {
      const list = document.createElement("ul");
      list.className = "campaign-list";
      campaign.diagnosis.findings.forEach((finding) => {
        const item = document.createElement("li");
        item.textContent = finding;
        list.appendChild(item);
      });
      actions.appendChild(list);
      if (campaign.diagnosis.ransac_available) {
        addButton(actions, "Aplicar RANSAC nos outliers", () => campaignPost("/api/campaigns/active/ransac"));
      }
    }
  }
  if (campaign.stage_index > 0) {
    addButton(actions, "Voltar", () => {
      if (!window.confirm("Voltar para a etapa anterior? As medições já gravadas permanecem.")) return;
      campaignPost("/api/campaigns/active/retreat");
    }, true);
  }
  if (campaign.gate.passed && stage !== "analyze_residuals") {
    addButton(actions, "Avançar", () => campaignPost("/api/campaigns/active/advance"));
  }
}

function acceptValidationImage(plane) {
  const height = Number(plane);
  campaignPost("/api/campaigns/active/validation/plane", { plan_z: height }).then((ok) => {
    if (!ok) return;
    campaignPost("/api/campaigns/active/captures", { decision: "accepted" });
  });
}

function chooseValidationPlane(plane) {
  chosenValidationPlane = plane;
  document.querySelectorAll("#campaign-actions [data-plane]").forEach((button) => {
    const chosen = Number(button.dataset.plane) === plane;
    button.className = chosen ? "button button-primary" : "button button-secondary";
    if (!button.textContent.includes("RMSE")) {
      button.textContent = chosen ? `Z ${plane} mm · escolhida` : `Z ${button.dataset.plane} mm`;
    }
  });
  const accept = [...document.querySelectorAll("#campaign-actions button")].find((button) => button.textContent.startsWith("Aceitar imagem em Z"));
  if (accept) accept.textContent = `Aceitar imagem em Z ${plane} mm`;
  campaignPost("/api/campaigns/active/validation/plane", { plan_z: plane }).then(async (ok) => {
    if (ok || chosenValidationPlane !== plane) return;
    chosenValidationPlane = null;
    campaignSignature = "";
    await refreshState();
  });
}

function paintFocus(campaign) {
  const node = document.getElementById("focus-meter");
  if (!node || !campaign?.focus) return;
  if (campaign.stage === "analyze_residuals") {
    node.hidden = true;
    node.textContent = "";
    return;
  }
  node.hidden = false;
  const focus = campaign.focus;
  if (focus.current === null || focus.current === undefined) {
    node.textContent = focus.status;
    return;
  }
  node.textContent = `Nitidez ${Number(focus.current).toFixed(0)} · máximo ${Number(focus.peak).toFixed(0)} · ${focus.status}`;
}

function addButton(parent, label, onClick, secondary = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = secondary ? "button button-secondary" : "button button-primary";
  button.textContent = label;
  button.addEventListener("click", onClick);
  parent.appendChild(button);
  return button;
}

document.getElementById("campaign-select").addEventListener("change", syncCampaignButtons);

document.getElementById("open-campaign").addEventListener("click", () => {
  const id = document.getElementById("campaign-select").value;
  if (!id) {
    toast("Escolha uma campanha para abrir.", "error");
    return;
  }
  resumeCampaign(id);
});

document.getElementById("delete-campaign").addEventListener("click", async () => {
  const select = document.getElementById("campaign-select");
  const id = select.value;
  if (!id) {
    toast("Escolha a campanha que deseja excluir.", "error");
    return;
  }
  const label = select.selectedOptions[0]?.textContent || "esta campanha";
  if (!window.confirm(`Excluir ${label}? As capturas desta campanha também saem.`)) return;
  try {
    await api(`/api/campaigns/${id}`, { method: "DELETE" });
    campaignSignature = "";
    select.dataset.signature = "";
    await refreshState();
    toast("Campanha excluída.");
  } catch (error) {
    toast(error.message, "error");
  }
});

document.getElementById("new-campaign").addEventListener("click", () => {
  const corners = app.config && app.config.board_inner_corners;
  if (corners && corners.length === 2) {
    document.getElementById("campaign-cols").value = corners[0];
    document.getElementById("campaign-rows").value = corners[1];
  }
  document.getElementById("campaign-dialog").showModal();
});

document.getElementById("campaign-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = document.getElementById("campaign-name").value.trim();
  const square = Number(document.getElementById("campaign-square").value);
  const pattern = [
    Number(document.getElementById("campaign-cols").value),
    Number(document.getElementById("campaign-rows").value),
  ];
  try {
    await api("/api/campaigns", { method: "POST", body: JSON.stringify({ name, square_size_mm: square, pattern }) });
    document.getElementById("campaign-dialog").close();
    campaignSignature = "";
    await refreshState();
    toast("Campanha aberta. Siga a etapa 1.");
  } catch (error) {
    toast(error.message, "error");
  }
});

window.renderCampaign = renderCampaign;
