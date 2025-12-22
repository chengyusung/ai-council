"""AI Council - LLM 委員會討論系統

啟動方式：
    uv run python main.py

或直接執行：
    python main.py
"""

import argparse
from ui.app import create_app
import config


def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(
        description="AI Council - LLM 委員會討論系統",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="伺服器主機位址 (預設: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7860,
        help="伺服器埠號 (預設: 7860)",
    )
    parser.add_argument(
        "--share",
        action="store_true",
        help="建立公開分享連結",
    )

    args = parser.parse_args()

    # 檢查設定
    errors = config.validate_config()
    if errors:
        print("設定警告：")
        for error in errors:
            print(f"  - {error}")
        print()
        print("請複製 .env.example 為 .env 並填入 API Keys")
        print()

    # 建立並啟動應用程式
    print("=" * 50)
    print("AI Council - LLM 委員會討論系統")
    print("=" * 50)
    print()
    print(f"啟動伺服器: http://{args.host}:{args.port}")
    print()

    app = create_app()
    app.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
    )


if __name__ == "__main__":
    main()
