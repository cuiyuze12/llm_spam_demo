import uuid
import boto3

# 固定使用一组 Agent ID 与 Alias ID
AGENT_ID = "KE5K7EJATO"
AGENT_ALIAS_ID = "5QE209YEBI"

# 每个会话独立 UUID
session_id = str(uuid.uuid1())

# 创建客户端（确保 AWS 权限没问题）
client = boto3.client("bedrock-agent-runtime", region_name="us-east-1")

def run_bedrock_agent(prompt: str) -> str:
    try:
        response = client.invoke_agent(
            inputText=prompt,
            agentId=AGENT_ID,
            agentAliasId=AGENT_ALIAS_ID,
            sessionId=session_id,
            enableTrace=True,
        )

        # 逐步取得 response 内容
        event_stream = response["completion"]
        full_text = ""
        classification = "b"  # デフォルトは一般知識

        for event in event_stream:
            if "chunk" in event:
                chunk_text = event["chunk"]["bytes"].decode("utf-8")
                full_text += chunk_text

                # 检查是否提到 action/function 或 knowledge base
                if '"type":"ActionGroupInvocation"' in chunk_text:
                    classification = "a"
                elif '"type":"KnowledgeBaseQuery"' in chunk_text:
                    classification = "c"

        #return full_text
        return {
            "text": full_text,
            "category": classification
        }
    except Exception as e:
        #return f"エラーが発生しました: {str(e)}"
        return {
            "text": f"エラーが発生しました: {str(e)}",
            "category": "エラー"
        }