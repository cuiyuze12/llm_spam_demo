from langchain_aws import ChatBedrock
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
import boto3


session = boto3.Session()
kb_client = session.client("bedrock-runtime", region_name="us-east-1")

# 初期化はグローバルに一度だけ行う（FastAPIの起動時）
retriever = AmazonKnowledgeBasesRetriever(
    knowledge_base_id="PFGPGVDWRJ",
    retrieval_config={"vectorSearchConfiguration": {"numberOfResults": 10}},
    region_name="us-east-1"  # 显式指定区域
)

prompt = ChatPromptTemplate.from_template(
    "以下のcontextに基づいて、できるだけ丁寧に日本語で回答してください。\n\nContext:\n{context}\n\n質問:\n{question}"
)


model = ChatBedrock(
    client=kb_client,
    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
    model_kwargs={"max_tokens": 1000},
)

# チェーンを構成
rag_chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | model
        | StrOutputParser()
)

# FastAPIから呼び出せる関数
def real_rag_answer(question: str) -> str:
    try:
        result = rag_chain.invoke(question)
        return result
    except Exception as e:
        return f"エラーが発生しました: {str(e)}"
