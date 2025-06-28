#from pkg_resources import get_distribution, DistributionNotFound

#pkgs = ["tiktoken", "torch"]

#for p in pkgs:
#   try:
#       v = get_distribution(p).version
#       print(f"{p} version: {v}")
#   except DistributionNotFound:
#       print(f"{p} not installed.")
import torch
import tiktoken




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

def load_model_and_tokenizer():
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

# if __name__ == "__main__":
# text_1 = (
#     "You are a winner you have been specially"
#     " selected to receive $1000 cash or a $2000 award."
# )
# 
# print(text_1 + "->" +  classify_review(
#     text_1, model, tokenizer, device, max_length=120
# ))
# 
# text_2 = (
#     "Hey, just wanted to check if we're still on"
#     " for dinner tonight? Let me know!"
# )
# 
# print(text_2 + "->" +  classify_review(
#     text_2, model, tokenizer, device, max_length=120
# ))


