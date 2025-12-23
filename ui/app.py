"""Gradio UI 模組"""

import random
import gradio as gr

import config
from models import SessionConfig, ModeratorConfig, MemberConfig
from council.session import Session


# 全域會議實例
current_session: Session | None = None


def get_model_choices() -> list[tuple[str, str]]:
    """取得模型選項"""
    return [(m["name"], m["id"]) for m in config.AVAILABLE_MODELS]


def create_app() -> gr.Blocks:
    """建立 Gradio 應用程式"""

    with gr.Blocks(
        title="AI Council - LLM 委員會討論系統",
    ) as app:
        gr.Markdown("# AI Council - LLM 委員會討論系統")
        gr.Markdown("讓多個 AI 模型一起討論主題，由主持人引導對話。")

        # 檢查設定
        errors = config.validate_config()
        if errors:
            gr.Markdown(
                "**設定警告**：\n" + "\n".join(f"- {e}" for e in errors),
            )

        with gr.Row():
            # 左側：設定區
            with gr.Column(scale=1):
                gr.Markdown("## 討論設定")

                topic_input = gr.Textbox(
                    label="討論主題",
                    placeholder="請輸入要討論的主題...",
                    lines=3,
                )

                with gr.Row():
                    rounds_input = gr.Number(
                        label="討論輪數",
                        value=config.DEFAULT_ROUNDS,
                        minimum=1,
                        maximum=10,
                        precision=0,
                    )
                    max_tokens_input = gr.Number(
                        label="每次回答 Token 上限",
                        value=config.DEFAULT_MAX_TOKENS,
                        minimum=100,
                        maximum=2000,
                        precision=0,
                    )

                gr.Markdown("### 主持人設定")
                moderator_model = gr.Dropdown(
                    label="主持人模型",
                    choices=get_model_choices(),
                    value=config.AVAILABLE_MODELS[0]["id"] if config.AVAILABLE_MODELS else None,
                )
                moderator_prompt = gr.Textbox(
                    label="主持人人設（選填）",
                    placeholder="例如：嚴謹的學術討論主持人",
                    lines=2,
                )

                gr.Markdown("### 委員會成員")
                gr.Markdown("*成員之間不能選擇相同模型*", elem_classes=["hint"])

                # 成員設定：5 個固定槽位，用 Dropdown 選擇模型
                member_dropdowns = []
                member_prompts = []
                default_models = [m["id"] for m in config.AVAILABLE_MODELS[:3]]  # 預設前 3 個

                for i in range(5):
                    with gr.Row():
                        model_dropdown = gr.Dropdown(
                            label=f"成員 {i+1}",
                            choices=[("（不參與）", "")] + get_model_choices(),
                            value=default_models[i] if i < len(default_models) else "",
                        )
                        prompt_input = gr.Textbox(
                            label="人設",
                            placeholder="選填",
                            scale=2,
                        )
                        member_dropdowns.append(model_dropdown)
                        member_prompts.append(prompt_input)

                # 控制按鈕
                gr.Markdown("### 控制")
                with gr.Row():
                    start_btn = gr.Button("開始討論", variant="primary")
                    stop_btn = gr.Button("停止", variant="stop")

                with gr.Row():
                    summary_btn = gr.Button("請主持人總結")

                # 名字對照表（討論開始後顯示）
                gr.Markdown("### 成員對照表")
                name_mapping_display = gr.Markdown("*討論開始後顯示*")

            # 右側：對話區
            with gr.Column(scale=2):
                gr.Markdown("## 討論進行中")

                status_text = gr.Markdown("狀態：等待開始")

                chatbot = gr.Chatbot(
                    label="討論內容",
                    height=500,
                )


        # 事件處理
        async def start_discussion(
            topic: str,
            rounds: int,
            max_tokens: int,
            mod_model: str,
            mod_prompt: str,
            *member_values,
        ):
            """開始討論"""
            global current_session

            if not topic.strip():
                yield (
                    [{"role": "assistant", "content": "請輸入討論主題"}],
                    "狀態：請輸入討論主題",
                    "*討論開始後顯示*",
                )
                return

            # 解析成員設定
            # member_values 結構：[model_id_1, ..., model_id_5, prompt_1, ..., prompt_5]
            num_slots = 5
            model_ids = member_values[:num_slots]
            prompts = member_values[num_slots:]

            # 分配隨機名字
            available_names = config.RANDOM_NAMES.copy()
            random.shuffle(available_names)

            members = []
            name_to_model = []  # 用於顯示對照表

            for model_id, prompt in zip(model_ids, prompts):
                if model_id:  # 有選模型才加入
                    # 分配隨機名字
                    alias = available_names.pop(0) if available_names else f"Member{len(members)+1}"
                    model_name = config.get_model_name(model_id)

                    members.append(MemberConfig(
                        model_id=model_id,
                        display_name=alias,  # 使用隨機名字
                        system_prompt=prompt or "",
                        enabled=True,
                    ))
                    name_to_model.append((alias, model_name))

            if not members:
                yield (
                    [{"role": "assistant", "content": "請至少選擇一位委員會成員"}],
                    "狀態：請至少選擇一位成員",
                    "*討論開始後顯示*",
                )
                return

            # 主持人名字
            moderator_alias = config.MODERATOR_NAME
            moderator_model_name = config.get_model_name(mod_model)

            # 建立對照表顯示
            mapping_lines = [f"🎤 **{moderator_alias}**（主持人）→ {moderator_model_name}"]
            for alias, model_name in name_to_model:
                mapping_lines.append(f"💬 **{alias}** → {model_name}")
            name_mapping_text = "\n\n".join(mapping_lines)

            # 建立會議設定
            session_config = SessionConfig(
                topic=topic,
                total_rounds=int(rounds),
                max_tokens=int(max_tokens),
                moderator=ModeratorConfig(
                    model_id=mod_model,
                    display_name=moderator_alias,  # 使用固定主持人名字
                    system_prompt=mod_prompt,
                ),
                members=members,
            )

            # 建立會議
            current_session = Session(session_config)

            # 執行討論
            messages = []
            current_content = ""
            current_speaker = ""

            async for event in current_session.run():
                if event.event_type == "system":
                    messages.append({
                        "role": "assistant",
                        "content": f"*{event.content}*",
                    })
                    yield (
                        messages.copy(),
                        f"狀態：{event.content}",
                        name_mapping_text,
                    )

                elif event.event_type in ("moderator", "member"):
                    # 成員顯示帽子 emoji，主持人顯示麥克風
                    if event.event_type == "member" and event.hat_emoji:
                        speaker_prefix = f"💬 {event.hat_emoji}"
                    elif event.event_type == "moderator":
                        speaker_prefix = "🎤"
                    else:
                        speaker_prefix = "💬"

                    # 帽子名稱（用於狀態顯示）
                    hat_suffix = f" [{event.hat_name}]" if event.hat_name else ""

                    if event.is_streaming and not event.is_final:
                        if event.speaker_name != current_speaker:
                            # 新的發言者
                            if current_speaker and current_content:
                                # 完成前一個
                                pass
                            current_speaker = event.speaker_name
                            current_content = event.content
                            messages.append({
                                "role": "assistant",
                                "content": f"**{speaker_prefix} {current_speaker}{hat_suffix}**\n\n{current_content}",
                            })
                        else:
                            # 繼續串流
                            current_content += event.content
                            if messages:
                                messages[-1]["content"] = f"**{speaker_prefix} {current_speaker}{hat_suffix}**\n\n{current_content}"

                        status_msg = f"狀態：{current_speaker}{hat_suffix} 發言中..."
                        if event.speech_index:
                            status_msg += f" (第 {event.speech_index} 次發言)"

                        yield (
                            messages.copy(),
                            status_msg,
                            name_mapping_text,
                        )

                    elif event.is_final:
                        # 發言完成
                        final_content = f"**{speaker_prefix} {event.speaker_name}{hat_suffix}**\n\n{event.content}"
                        if event.search_sources:
                            sources = "\n".join(f"- {s}" for s in event.search_sources[:3])
                            final_content += f"\n\n📎 **來源**:\n{sources}"

                        if messages and current_speaker == event.speaker_name:
                            messages[-1]["content"] = final_content
                        else:
                            messages.append({
                                "role": "assistant",
                                "content": final_content,
                            })

                        current_speaker = ""
                        current_content = ""

                        yield (
                            messages.copy(),
                            f"狀態：進行中 (第 {event.speech_index} 次發言)" if event.speech_index else "狀態：進行中",
                            name_mapping_text,
                        )

            yield (
                messages.copy(),
                "狀態：討論結束",
                name_mapping_text,
            )

        def stop_discussion():
            """停止討論"""
            global current_session
            if current_session:
                current_session.request_stop()
            return "狀態：已請求停止"

        def request_summary():
            """請求總結"""
            global current_session
            if current_session:
                current_session.request_summary()
            return "狀態：已請求總結"

        # 模型互斥邏輯：當一個成員選了某模型，其他成員不能選同樣的
        def update_member_choices(*selected_models):
            """更新各成員的可選模型，排除已被其他成員選擇的"""
            all_choices = [("（不參與）", "")] + get_model_choices()
            results = []

            for i, current in enumerate(selected_models):
                # 收集其他成員已選的模型
                others_selected = [m for j, m in enumerate(selected_models) if j != i and m]
                # 過濾掉已被選的（但保留自己目前選的）
                available = [
                    (name, mid) for name, mid in all_choices
                    if mid not in others_selected or mid == current or mid == ""
                ]
                results.append(gr.update(choices=available, value=current))

            return results

        # 綁定成員 Dropdown 的 change 事件實現互斥
        for dropdown in member_dropdowns:
            dropdown.change(
                fn=update_member_choices,
                inputs=member_dropdowns,
                outputs=member_dropdowns,
            )

        # 綁定開始討論按鈕
        # inputs 順序：基本設定 + 所有成員模型 + 所有成員人設
        start_btn.click(
            fn=start_discussion,
            inputs=[
                topic_input,
                rounds_input,
                max_tokens_input,
                moderator_model,
                moderator_prompt,
                *member_dropdowns,
                *member_prompts,
            ],
            outputs=[chatbot, status_text, name_mapping_display],
        )

        stop_btn.click(
            fn=stop_discussion,
            outputs=[status_text],
        )

        summary_btn.click(
            fn=request_summary,
            outputs=[status_text],
        )

    return app
