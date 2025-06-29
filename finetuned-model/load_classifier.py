import torch
import tiktoken
import os
import boto3
from mygpt import GPTModel


BASE_CONFIG = {
    "vocab_size": 50257,     # Vocabulary size
    "context_length": 1024,  # Context length
    "drop_rate": 0.0,        # Dropout rate
    "qkv_bias": True         # Query-key-value bias
}

model_configs = {
    "gpt2-small (124M)": {"emb_dim": 768, "n_layers": 12, "n_heads": 12},
    "gpt2-medium (355M)": {"emb_dim": 1024, "n_layers": 24, "n_heads": 16},
    "gpt2-large (774M)": {"emb_dim": 1280, "n_layers": 36, "n_heads": 20},
    "gpt2-xl (1558M)": {"emb_dim": 1600, "n_layers": 48, "n_heads": 25},
}

CHOOSE_MODEL = "gpt2-small (124M)"

BASE_CONFIG.update(model_configs[CHOOSE_MODEL])

def download_model_from_s3(bucket_name, object_key, local_path):
    if not os.path.exists(local_path):
        print(f"Downloading model from s3://{bucket_name}/{object_key} ...")
        s3 = boto3.client("s3")
        s3.download_file(bucket_name, object_key, local_path)
        print("Download complete.")
    else:
        print("Model file already exists. Skipping download.")

def load_model_and_tokenizer():
    model_path = "review_classifier.pth"
    download_model_from_s3(
        bucket_name="llm-demo-models",
        object_key="models/review_classifier.pth",
        local_path=model_path
    )

    from pathlib import Path

    finetuned_model_path = Path("review_classifier.pth")
    if not finetuned_model_path.exists():
        print(
            f"Could not find '{finetuned_model_path}'.\n"
            "Run the `ch06.ipynb` notebook to finetune and save the finetuned model."
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    tokenizer = tiktoken.get_encoding("gpt2")
    
    # Initialize base model
    model = GPTModel(BASE_CONFIG)
    # Convert model to classifier as in section 6.5 in ch06.ipynb
    num_classes = 2
    model.out_head = torch.nn.Linear(in_features=BASE_CONFIG["emb_dim"], out_features=num_classes)

    # Then load pretrained weights
    model.load_state_dict(torch.load("review_classifier.pth", map_location=device, weights_only=True))
    model.to(device)
    model.eval();
    
    return model, tokenizer, device

def classify_review(text, model, tokenizer, device, max_length=120, pad_token_id=50256):
    model.eval()

    # Prepare inputs to the model
    input_ids = tokenizer.encode(text)
    supported_context_length = model.pos_emb.weight.shape[0]

    # Truncate sequences if they too long
    input_ids = input_ids[:min(max_length, supported_context_length)]

    # Pad sequences to the longest sequence
    input_ids += [pad_token_id] * (max_length - len(input_ids))
    input_tensor = torch.tensor(input_ids, device=device).unsqueeze(0) # add batch dimension

    # Model inference
    with torch.no_grad():
        logits = model(input_tensor.to(device))[:, -1, :]  # Logits of the last output token
        
        print("logits shape:", logits.shape)
        print("logits:", logits)
    
    predicted_label = torch.argmax(logits, dim=-1).item()
    
    print("predicted_label: ", predicted_label)

    # Return the classified result
    return "spam" if predicted_label == 1 else "not spam"

