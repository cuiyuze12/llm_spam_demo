


def run_training(contents) :
    return 0.2
'''
        texts, labels = [], []
        lines = contents.decode("utf-8").splitlines()
        reader = csv.reader(lines)
        for row in reader:
            if len(row) == 2:
                texts.append(row[0])
                labels.append(int(row[1]))


        # 简单统计准确率（模拟训练）
        correct = 0
        for text, label in zip(texts, labels):
            pred_label, _ = classify_review(text, model, tokenizer, device)
            correct += (pred_label == "spam" if label == 1 else pred_label == "not spam")

        acc = correct / len(texts)

        # 保存训练结果图像
        os.makedirs("static", exist_ok=True)
        plt.figure()
        plt.title("Accuracy")
        plt.bar(["accuracy"], [acc])
        plt.ylim(0, 1)
        plt.savefig("static/train_result.png")
        plt.close()
'''