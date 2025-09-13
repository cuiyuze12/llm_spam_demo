
# 🧠 AIマルチ機能デモ

このプロジェクトは、**自作の軽量LLM・RAG・AIエージェント**を統合した多機能AIデモWebアプリケーションです。  
以下の4つのセクションで、AIの異なる活用方法を体験できます：

- ✅ GPT-2ベースの英語テキスト分類と生成（自作LLM）
- 📚 Bedrock + Knowledge Baseによる社内文書検索応答（自作RAG）
- 🧑‍💼 Bedrock Agent によるAIエージェントチャット（自作AIエージェント）
- 🧾 発注AIエージェント：自然言語→構造化JSON→注文書PDF（日本語対応）

▶️ デモサイト： [https://wonderlusia.site](https://wonderlusia.site)

---

## 🔍 機能一覧

### 🟦 自作LLM（英語対応）
- **迷惑メール分類**：GPT-2に英語スパム分類のファインチューニングを実施。任意の英語メッセージを分類可能。
- **命令応答生成**：命令タスク（Instruction Tuning）で学習済みモデルにより、指定フォーマットの英語指示に応答を生成。

※ モデル学習は Google Colab 上で実施し、現在は EC2 上の Web アプリからリアルタイムで推論を行っています。

---

### 🟩 自作RAG（日本語対応）
- Amazon Bedrock の Knowledge Base 機能を活用。
- JPXの決算説明資料を対象としたナレッジベースを構築。
- 自然な日本語による文書検索・要約応答を提供します。

---

### 🟥 自作AIエージェント（日本語対応）
- Bedrock Agent ＋ ReAct（Reasoning + Acting）手法によるマルチエージェントチャット。
- ユーザーの質問内容に応じて以下の3つの処理を自動で切り替え：
  1. **AWSの最新情報取得**（Lambda + SerpAPI）
  2. **JPX関連の文書検索**（Bedrock RAG）
  3. **その他の質問対応**（Claude 3）


---

### 🧾 発注AIエージェント（日本語対応）
- **概要**：日本語の依頼文から LLM が発注内容（発注者・品目・数量・単価 等）を抽出し、バックエンドで **Pydantic によるスキーマ検証・正規化** を行った上で **構造化 JSON（Order）** を生成します。必須項目が揃えば **ワンクリックで注文書PDF** をダウンロードできます。
- **できること**
  - 自然言語 → 構造化 JSON（Order）への変換
  - 不足項目がある場合の **インタラクティブ補完**（必要な項目だけ質問）
  - PDF 出力
- **使い方**
  1. テキストボックスに日本語で発注内容を入力し「対話を開始」。  
  2. 不足があれば追加入力欄に回答。  
  3. すべて揃うと「注文書（PDF）をダウンロード」ボタンが有効化。  
- **必須項目（本デモ）**  
  発注者名・品目名・品目コード・数量・単価（5項目に限定）  
  ※ 本デモでは要件をシンプルにするため上記のみ必須にしています。


---

## 🛠 技術スタック

### 💻 使用言語・ライブラリ
- Python
  - FastAPI
  - PyTorch
  - tiktoken
  - langchain

### ☁️ 使用サービス・外部API
- **AWS**
  - EC2（Webアプリホスティング）
  - S3（ファイル保存）
  - Bedrock（Claude 3, Knowledge Base, Agent）
  - Lambda（API連携）
- **その他**
  - Claude 3（via Bedrock）
  - Pinecone（ベクトルDB）
  - SerpAPI（Google検索結果取得）
  - Google Colab（モデル訓練環境）

---

## 🚀 実行方法

以下のコマンドでアプリを起動できます：

```bash
uvicorn api_server:app --host 0.0.0.0 --port 5000
```

アプリURL：
- [https://wonderlusia.site](https://wonderlusia.site) 

---

## 🖼️ 画面イメージ

### ▶️ 自作LLM（スパム分類 & 応答生成）
![LLMデモ画面](pics/img1.png)

---

### ▶️ 自作RAG（社内資料からの日本語質問応答）
![RAGデモ画面](pics/img2.png)

---

### ▶️ 自作AIエージェント（チャット式応答）
![エージェントデモ画面](pics/img3.png)

---

## 📄 ライセンス

このプロジェクトは教育・技術デモの目的で公開されています。商用利用はご遠慮ください。

---


---

## 🔄 Git Flow 運用について

このリポジトリは Git Flow に基づいて管理されています。  
GitFlowのブランチ戦略としては、`main` / `develop` / `feature/*` / `release/*` / `hotfix/*` の構成を採用することですが、
本プロジェクトは小規模のため`main` / `feature/*` の構成になっています。

🔗 関連ブログ投稿（執筆者：崔 玉澤）  
👉 [バックオフィスシステム開発におけるGitflowの使い方について - KINTO Technologies Tech Blog](https://blog.kinto-technologies.com/posts/2022-12-03-gitflow/)

---

## ⚙️ GitHub Actions（CI/CD）

本リポジトリには以下の GitHub Actions ワークフローが設定されています：

- **release**：指定ブランチのコードをEC2へリリース
- **deploy**：リリースが完了後にWebアプリケーションを起動
- **stop**：Webアプリケーションを手動で停止

ワークフローは `.github/workflows/` フォルダ内に構成されています。


## 🙋‍♂️ 開発者情報

**崔 玉澤（Yuze Cui）**

- ITエンジニア・プロジェクトマネージャー
- G検定・AI実装者検定A級・Python3データ分析認定取得
- LLMおよびAWS Bedrockを活用した生成AIソリューション開発に取り組んでいます

ご質問・ご連絡は GitHub 上のIssueよりお気軽にどうぞ。
