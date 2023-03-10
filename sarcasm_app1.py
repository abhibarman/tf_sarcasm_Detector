import csv
import glob
import os
from pathlib import Path
import re
from uuid import uuid4
from clearml import Dataset, Model, Task
import gradio as gr
import joblib
import time
# from transformers import pipeline
import tensorflow as tf
import pickle


#task = Task.init('tf_sarcasm_detector', "tf_sarcasm_inference",'inference')

def get_model_And_tokenizer(trainig_task_id):

    train_task = Task.get_task(trainig_task_id)
    transformer_model_path = train_task.models.data['output'][0].get_local_copy()
    model = tf.keras.models.load_model(transformer_model_path)

    tokenizer_path  = train_task.artifacts['local file'].get_local_copy()
    with open(tokenizer_path, 'rb') as handle:
        tokenizer = pickle.load(handle)

    return model, tokenizer

model, tokenizer = get_model_And_tokenizer('caec4160faed4bafb009721f2fcf1e98')

sklearn_model_path = Model(model_id="9ac90d026bd044209958ffd80433a761").get_local_copy()

sklearn_pipeline = joblib.load(sklearn_model_path)


def classify_DNN(sentence):
    start = time.time()
    sequences = tokenizer.texts_to_sequences([sentence])
    padded =tf.keras.preprocessing.sequence.pad_sequences(sequences, maxlen=100, padding='post', truncating='post')
    score = model.predict(padded)[0]
    if score[0] > 0.5:
        label = 'SARCASTIC'
    else:
        label = 'NORMAL'
    time_taken = time.time() - start
    return f"LABEL: {label}\nCERTAINTY: {score[0]:.2f}\nCOMPUTE TIME: {time_taken:.5f}"


def classify_logistic(sentence):
    start = time.time()
    sarcastic = sklearn_pipeline.predict_proba([sentence])[0]
    time_taken = time.time() - start
    if sarcastic[0] > sarcastic[1]:
        label = "NORMAL"
        score = sarcastic[0]
    else:
        label = "SARCASTIC"
        score = sarcastic[1]
    return f"LABEL: {label}\nCERTAINTY: {score:.2f}\nCOMPUTE TIME: {time_taken:.5f}"

def parse_output_to_label(output):
    if not output.startswith("LABEL"):
        return [output]
    # Extract the label and certainty value from the text
    result = re.search(r"LABEL: (\w+)\nCERTAINTY: ([\d\.]+)", output)

    # Check if the label is "NORMAL" or "SARCASTIC"
    if result:
        label = result.group(1)
        certainty = float(result.group(2))
        if label == "NORMAL":
            return [0]
        elif label == "SARCASTIC":
            return [1]

def log_to_csv(text, model_output, csv_name, count, prefix=""):
    os.makedirs("flagged", exist_ok=True)
    log_filepath = Path("flagged") / (prefix + str(csv_name))
    csv_data = [text] + parse_output_to_label(model_output)

    with open(log_filepath, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        if os.stat(log_filepath).st_size > 0:
            pass
        else:
            writer.writerow(['headline', 'is_sarcastic'])
        writer.writerow(csv_data)
    
    new_count = count + 1
    return new_count, f"{new_count} labeled samples"

def create_clearml_dataset_version(csv_filename, amount, counter):
    paths = glob.glob(str(Path("flagged") / f"*_{csv_filename}"))
    if paths:
        latest_clearml_dataset_id = Dataset.get(dataset_project="Sana1_sarcasm_detector", dataset_name="sarcasm_dataset").id
        print(f"{latest_clearml_dataset_id=}")
        updated_dataset = Dataset.create(
            dataset_project="Sana1_sarcasm_detector",
            dataset_name="sarcasm_dataset",
            parent_datasets=[latest_clearml_dataset_id]
        )
        [updated_dataset.add_files(path) for path in paths]
        updated_dataset.finalize(auto_upload=True)
        
        [os.remove(path) for path in paths]

        return f"{uuid4()}.csv", 0, "0 labeled samples"
    return csv_filename, amount, counter

demo = gr.Blocks(css="style.css")
with demo:
    # transformers_callback = ClearMLDatasetLogger()
    # logistic_callback = ClearMLDatasetLogger()
    amount_labeled_var = gr.State(0)
    csv_filename = gr.State(f"{uuid4()}.csv")

    
    with gr.Row():
        logo_image = gr.Image(value="JARVIS_Logo.png", source="upload",elem_id="img1",show_label=False)
        gr.Label("SARCASM DETECTION", elem_id="Warning")

    with gr.Row():
        with gr.Row():
            with gr.Column():
                text = gr.Textbox(label="Model input sentence")
                b1 = gr.Button("Classify Sarcasm",elem_id="Warning1")
            
        with gr.Row():
            with gr.Column():
                output_transformer = gr.Textbox(label="Model 1")
                b2 = gr.Button("Model 1 was Wrong",elem_id="Warning1")
            with gr.Column():
                output_logistic = gr.Textbox(label="Model 2")
                b3 = gr.Button("Model 2 was Wrong",elem_id="Warning1")

        with gr.Row().style(equal_height=True):
            with gr.Column():
                counter = gr.Label("0 labeled samples")
            #with gr.Column():
                b4 = gr.Button(f"Package Labeled Samples",elem_id="Warning1")

    # This needs to be called at some point prior to the first call to callback.flag()
    # transformers_callback.setup([text, output_transformer, csv_filename, amount_labeled_var], "flagged_transformer")
    # logistic_callback.setup([text, output_logistic, csv_filename, amount_labeled_var], "flagged_logistic")

    # Run the models
    b1.click(classify_DNN, inputs=text, outputs=output_transformer)
    b1.click(classify_logistic, inputs=text, outputs=output_logistic)

    # Serve as a labeling tool
    b2.click(lambda *args: log_to_csv(*args, prefix="dnn_"), inputs=[text, output_transformer, csv_filename, amount_labeled_var], outputs=[amount_labeled_var, counter])
    b3.click(lambda *args: log_to_csv(*args, prefix="logistic_"), inputs=[text, output_logistic, csv_filename, amount_labeled_var], outputs=[amount_labeled_var, counter])

    # Package the current labels and ship them as a ClearML Dataset
    b4.click(create_clearml_dataset_version, inputs=[csv_filename, amount_labeled_var, counter], outputs=[csv_filename, amount_labeled_var, counter])
        #demo1.launch()
demo.launch()#share=True)logo_image = gr.Image(value="/home/oem/Demo1Abhijit/tf_sarcasm_Detector/JARVIS_Logo1.png", shape=[], source="upload", show_label=False)
#task.close()




