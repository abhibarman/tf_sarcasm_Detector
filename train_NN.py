import tensorflow as tf
import pickle
from pathlib import Path
from clearml import Dataset, Task, OutputModel
import pandas as pd
import os
import numpy as np
from utils import plot_graphs, plot_confusion_matrix
import matplotlib.pyplot as plt

class SarcasmTrainer:
       

       def __init__(self, params) -> None:
              self.vocab_size = params['vocab_size']
              self.embedding_dim = params['embedding_dim']
              self.num_epochs = params['num_epochs']
              self.max_length = params['max_length']
              self.subset_size = params['subset_size']
              self.trunc_type=params['trunc_type']
              self.padding_type=params['padding_type']
              self.seed = params['seed']
              self.subset_size = params['subset_size']

              self.oov_tok = "<OOV>"
              self.tokenizer = None
              self.model = self.build_model()
              

       def build_model(self):
             model = tf.keras.Sequential([
                tf.keras.layers.Embedding(self.vocab_size, self.embedding_dim, input_length=self.max_length),
                tf.keras.layers.GlobalAveragePooling1D(),
                tf.keras.layers.Dense(24, activation='relu'),
                tf.keras.layers.Dense(1, activation='sigmoid')])
             model.compile(loss=tf.keras.losses.binary_crossentropy,optimizer='adam',metrics=['accuracy'])
             return model
       

       def get_data(self):
                local_dataset_path = Path(Dataset.get(
                    dataset_project="sarcasm_detector",dataset_name="sarcasm_dataset",alias="sarcasm_dataset"
                ).get_local_copy())

                data_files=[str(local_dataset_path / csv_path) for csv_path in os.listdir(local_dataset_path)]
                data = []
                for filename in data_files:
                    df = pd.read_csv(filename)#, sep='\t')
                    data.append(df)
                data = pd.concat(data, axis=0, ignore_index=True)

                if self.subset_size:
                      data = data[:self.subset_size]
                ratio = 9/10
                training_sentences = data.iloc[:int(self.subset_size * ratio),0] 
                testing_sentences = data.iloc[int(self.subset_size * ratio):,0]
                training_labels = data.iloc[:int(self.subset_size * ratio),1] 
                testing_labels = data.iloc[int(self.subset_size * ratio):,1]
                return (training_sentences,testing_sentences,training_labels,testing_labels)
       
       
       def tokenize(self):
            if self.tokenizer is None:
                  self.tokenizer = tf.keras.preprocessing.text.Tokenizer(num_words=self.vocab_size, oov_token=self.oov_tok)

            training_sentences,testing_sentences,training_labels,testing_labels = self.get_data()

            self.tokenizer.fit_on_texts(training_sentences)

            #word_index = self.tokenizer.word_index

            training_sequences = self.tokenizer.texts_to_sequences(training_sentences)
            training_padded = tf.keras.preprocessing.sequence.pad_sequences(training_sequences, maxlen=self.max_length, 
                                            padding=self.padding_type, truncating=self.trunc_type)

            testing_sequences = self.tokenizer.texts_to_sequences(testing_sentences)
            testing_padded = tf.keras.preprocessing.sequence.pad_sequences(testing_sequences, maxlen=self.max_length, padding=self.padding_type, truncating=self.trunc_type)

            # Need this block to get it to work with TensorFlow 2.x

            training_padded = np.array(training_padded)
            training_labels = np.array(training_labels)
            testing_padded = np.array(testing_padded)
            testing_labels = np.array(testing_labels)

            return (training_padded,training_labels, testing_padded, testing_labels)
       
       
       def train(self):
             training_padded,training_labels, testing_padded, testing_labels = self.tokenize()
             history = self.model.fit(training_padded, training_labels, epochs=self.num_epochs, 
                                      validation_data=(testing_padded, testing_labels), verbose=2,)
             
             plot_graphs(history=history, string='accuracy')
             plot_graphs(history=history, string='loss')

             y_pred = self.model.predict(training_padded)
             y_pred[y_pred > 0.5] = 1
             y_pred[y_pred <= 0.5] = 0

             y_pred_test = self.model.predict(testing_padded)
             y_pred_test[y_pred_test > 0.5] = 1
             y_pred_test[y_pred_test <= 0.5] = 0

             plot_confusion_matrix(training_labels,y_pred,["NORMAL", "SARCASTIC"],title='Training Confusion matrix',cmap= plt.cm.RdPu)
             plot_confusion_matrix(testing_labels,y_pred_test,["NORMAL", "SARCASTIC"],title='Validation Confusion matrix',cmap= plt.cm.BuGn)

             self.model.save('sarcasm_dnn_model.h5')

             #Save the tokenizer
             with open('tokenizer.pickle', 'wb') as handle:
                   pickle.dump(self.tokenizer, handle, protocol=pickle.HIGHEST_PROTOCOL)
             Task.current_task().upload_artifact('local file', artifact_object=os.path.join('tokenizer.pickle'))
            

if __name__ == '__main__':
    #Task.add_requirements("torch")
    task = Task.init(project_name="sarcasm_detector", task_name="TF 2.0 Sequence Model Training")

    params = {
          'vocab_size' : 10000,
          'embedding_dim' : 16,
          'num_epochs' : 50,
          'max_length' : 100,
          'subset_size' : 1000,
          'trunc_type':'post',
          'padding_type':'post',
          'seed':42
    }
    task.connect(params)
    sarcasm_trainer = SarcasmTrainer(params)
    sarcasm_trainer.train()      




