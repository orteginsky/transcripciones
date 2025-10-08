# src/orchestration/tasks.py
async def process_audio(path_mp3: Path, llm: VertexLLMClient, settings: Settings) -> Path:
    wav_path = audio_utils.to_wav_mono16k(path_mp3, settings.WORK_DIR)
    transcript = await stt_vertex.transcribe(wav_path, settings)

    # Renderizar prompt
    prompt = render_template("analysis_template.md.j2", {
        "transcript": transcript.text,
        "duration_sec": transcript.duration_sec,
        "speakers": transcript.speakers,
    })

    raw = llm.generate(prompt=prompt, system=load_template("base_instructions.md.j2"))

    # Validar → objeto Report
    report = schemas.Report.model_validate_json(safe_coerce_json(raw))

    # Render a PDF
    html = render_template("report.html.j2", {"report": report, "source": path_mp3.name})
    pdf_path = pdf.render(html, out_dir=settings.OUTPUT_DIR)
    return pdf_path
