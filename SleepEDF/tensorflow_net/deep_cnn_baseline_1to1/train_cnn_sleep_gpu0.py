import os
os.environ["CUDA_VISIBLE_DEVICES"]="0,-1"
import numpy as np
import tensorflow as tf

#from tensorflow.python.client import device_lib
#print(device_lib.list_local_devices())

import shutil, sys
from datetime import datetime
import h5py

from cnn_sleep_config import Config
from cnn_sleep import CNN_Sleep
from datagenerator_from_list_v2 import DataGenerator
from equaldatagenerator_from_list_v2 import EqualDataGenerator
from datagenerator_nchannel import DataGeneratorNChannel
from equaldatagenerator_nchannel import EqualDataGeneratorNChannel

from scipy.io import loadmat

from sklearn.metrics import f1_score
from sklearn.metrics import accuracy_score
from sklearn.metrics import cohen_kappa_score

import time

# Parameters
# ==================================================

# Misc Parameters
tf.app.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.app.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")

# My Parameters
tf.app.flags.DEFINE_string("eeg_train_data", "../train_data.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("eeg_eval_data", "../data/eval_data_1.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("eeg_test_data", "../test_data.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("eog_train_data", "../train_data.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("eog_eval_data", "../data/eval_data_1.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("eog_test_data", "../test_data.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("emg_train_data", "../train_data.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("emg_eval_data", "../data/eval_data_1.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("emg_test_data", "../test_data.mat", "Point to directory of input data")
tf.app.flags.DEFINE_string("out_dir", "./output/", "Point to output directory")
tf.app.flags.DEFINE_string("checkpoint_dir", "./checkpoint/", "Point to checkpoint directory")

tf.app.flags.DEFINE_float("dropout_keep_prob", 0.8, "Dropout keep probability (default: 0.8)")
tf.app.flags.DEFINE_float("dropout_keep_prob_conv", 0.8, "Convolutional dropout keep probability (default: 0.8)")

tf.app.flags.DEFINE_string("eeg_pretrainedfb_path", "./output/filterbank.mat", "Point to the pretrainedfb mat file")
tf.app.flags.DEFINE_string("eog_pretrainedfb_path", "./output/filterbank.mat", "Point to the pretrainedfb mat file")
tf.app.flags.DEFINE_string("emg_pretrainedfb_path", "./output/filterbank.mat", "Point to the pretrainedfb mat file")

FLAGS = tf.app.flags.FLAGS
print("\nParameters:")
for attr, value in sorted(FLAGS.__flags.items()): # python3
    print("{}={}".format(attr.upper(), value))
print("")

# path where some output are stored
out_path = os.path.abspath(os.path.join(os.path.curdir,FLAGS.out_dir))
# path where checkpoint models are stored
checkpoint_path = os.path.abspath(os.path.join(out_path,FLAGS.checkpoint_dir))
if not os.path.isdir(os.path.abspath(out_path)): os.makedirs(os.path.abspath(out_path))
if not os.path.isdir(os.path.abspath(checkpoint_path)): os.makedirs(os.path.abspath(checkpoint_path))

config = Config()
config.dropout_keep_prob = FLAGS.dropout_keep_prob
config.dropout_keep_prob_conv = FLAGS.dropout_keep_prob_conv

eeg_active = ((FLAGS.eeg_train_data != "") & (FLAGS.eeg_test_data != ""))
eog_active = ((FLAGS.eog_train_data != "") & (FLAGS.eog_test_data != ""))
emg_active = ((FLAGS.emg_train_data != "") & (FLAGS.emg_test_data != ""))

num_channel = 0

if (eeg_active):
    print("eeg active")
    num_channel += 1

    # Initalize the data generator seperately for the training, validation, and test sets
    eeg_train_gen = EqualDataGenerator(os.path.abspath(FLAGS.eeg_train_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    eeg_test_gen = DataGenerator(os.path.abspath(FLAGS.eeg_test_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    eeg_eval_gen = DataGenerator(os.path.abspath(FLAGS.eeg_eval_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    # load pretrained filterhanks and do filtering first
    eeg_filter = loadmat(FLAGS.eeg_pretrainedfb_path)
    Wfb = eeg_filter['Wfb']
    eeg_train_gen.filter_with_filterbank(Wfb)
    eeg_test_gen.filter_with_filterbank(Wfb)
    eeg_eval_gen.filter_with_filterbank(Wfb)
    del Wfb, eeg_filter

    # normalization here
    X = eeg_train_gen.X
    X = np.reshape(X,(eeg_train_gen.data_size*eeg_train_gen.data_shape[0], eeg_train_gen.data_shape[1]))
    meanX = X.mean(axis=0)
    stdX = X.std(axis=0)
    X = (X - meanX) / stdX
    eeg_train_gen.X = np.reshape(X, (eeg_train_gen.data_size, eeg_train_gen.data_shape[0], eeg_train_gen.data_shape[1]))

    X = eeg_eval_gen.X
    X = np.reshape(X,(eeg_eval_gen.data_size*eeg_eval_gen.data_shape[0], eeg_eval_gen.data_shape[1]))
    X = (X - meanX) / stdX
    eeg_eval_gen.X = np.reshape(X, (eeg_eval_gen.data_size, eeg_eval_gen.data_shape[0], eeg_eval_gen.data_shape[1]))

    X = eeg_test_gen.X
    X = np.reshape(X,(eeg_test_gen.data_size*eeg_test_gen.data_shape[0], eeg_test_gen.data_shape[1]))
    X = (X - meanX) / stdX
    eeg_test_gen.X = np.reshape(X, (eeg_test_gen.data_size, eeg_test_gen.data_shape[0], eeg_test_gen.data_shape[1]))
    del X


if (eog_active):
    print("eog active")
    num_channel += 1

    # Initalize the data generator seperately for the training, validation, and test sets
    eog_train_gen = EqualDataGenerator(os.path.abspath(FLAGS.eog_train_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    eog_test_gen = DataGenerator(os.path.abspath(FLAGS.eog_test_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    eog_eval_gen = DataGenerator(os.path.abspath(FLAGS.eog_eval_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    # load pretrained filterhanks and do filtering first
    eog_filter = loadmat(FLAGS.eog_pretrainedfb_path)
    Wfb = eog_filter['Wfb']
    eog_train_gen.filter_with_filterbank(Wfb)
    eog_test_gen.filter_with_filterbank(Wfb)
    eog_eval_gen.filter_with_filterbank(Wfb)
    del Wfb, eog_filter

    # normalization here
    X = eog_train_gen.X
    X = np.reshape(X,(eog_train_gen.data_size*eog_train_gen.data_shape[0], eog_train_gen.data_shape[1]))
    meanX = X.mean(axis=0)
    stdX = X.std(axis=0)
    X = (X - meanX) / stdX
    eog_train_gen.X = np.reshape(X, (eog_train_gen.data_size, eog_train_gen.data_shape[0], eog_train_gen.data_shape[1]))

    X = eog_eval_gen.X
    X = np.reshape(X,(eog_eval_gen.data_size*eog_eval_gen.data_shape[0], eog_eval_gen.data_shape[1]))
    X = (X - meanX) / stdX
    eog_eval_gen.X = np.reshape(X, (eog_eval_gen.data_size, eog_eval_gen.data_shape[0], eog_eval_gen.data_shape[1]))

    X = eog_test_gen.X
    X = np.reshape(X,(eog_test_gen.data_size*eog_test_gen.data_shape[0], eog_test_gen.data_shape[1]))
    X = (X - meanX) / stdX
    eog_test_gen.X = np.reshape(X, (eog_test_gen.data_size, eog_test_gen.data_shape[0], eog_test_gen.data_shape[1]))
    del X

if (emg_active):
    print("emg active")
    num_channel += 1

    # Initalize the data generator seperately for the training, validation, and test sets
    emg_train_gen = EqualDataGenerator(os.path.abspath(FLAGS.emg_train_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    emg_test_gen = DataGenerator(os.path.abspath(FLAGS.emg_test_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    emg_eval_gen = DataGenerator(os.path.abspath(FLAGS.emg_eval_data), data_shape=[config.n_time, config.n_dim], shuffle = False)
    # load pretrained filterhanks and do filtering first
    emg_filter = loadmat(FLAGS.emg_pretrainedfb_path)
    Wfb = emg_filter['Wfb']
    emg_train_gen.filter_with_filterbank(Wfb)
    emg_test_gen.filter_with_filterbank(Wfb)
    emg_eval_gen.filter_with_filterbank(Wfb)
    del Wfb, emg_filter

    # normalization here
    X = emg_train_gen.X
    X = np.reshape(X,(emg_train_gen.data_size*emg_train_gen.data_shape[0], emg_train_gen.data_shape[1]))
    meanX = X.mean(axis=0)
    stdX = X.std(axis=0)
    X = (X - meanX) / stdX
    emg_train_gen.X = np.reshape(X, (emg_train_gen.data_size, emg_train_gen.data_shape[0], emg_train_gen.data_shape[1]))

    X = emg_eval_gen.X
    X = np.reshape(X,(emg_eval_gen.data_size*emg_eval_gen.data_shape[0], emg_eval_gen.data_shape[1]))
    X = (X - meanX) / stdX
    emg_eval_gen.X = np.reshape(X, (emg_eval_gen.data_size, emg_eval_gen.data_shape[0], emg_eval_gen.data_shape[1]))

    X = emg_test_gen.X
    X = np.reshape(X,(emg_test_gen.data_size*emg_test_gen.data_shape[0], emg_test_gen.data_shape[1]))
    X = (X - meanX) / stdX
    emg_test_gen.X = np.reshape(X, (emg_test_gen.data_size, emg_test_gen.data_shape[0], emg_test_gen.data_shape[1]))
    del X

config.n_dim = eeg_train_gen.data_shape[1] # update the frequency dimension after filtering
config.n_channel = num_channel # update the number of channels


train_generator = EqualDataGeneratorNChannel(data_shape=[config.n_time, config.n_dim, num_channel], shuffle = False)
test_generator = DataGeneratorNChannel(data_shape=[config.n_time, config.n_dim, num_channel], shuffle = False)
eval_generator = DataGeneratorNChannel(data_shape=[config.n_time, config.n_dim, num_channel], shuffle = False)

# expanding and concatenation
if(num_channel == 1):
    train_generator.X = np.expand_dims(eeg_train_gen.X,axis=3)
    test_generator.X = np.expand_dims(eeg_test_gen.X,axis=3)
    eval_generator.X = np.expand_dims(eeg_eval_gen.X,axis=3)
elif(num_channel == 2):
    train_generator.X = np.concatenate((np.expand_dims(eeg_train_gen.X,axis=3),
                                        np.expand_dims(eog_train_gen.X,axis=3)), axis=-1)
    test_generator.X = np.concatenate((np.expand_dims(eeg_test_gen.X,axis=3),
                                        np.expand_dims(eog_test_gen.X,axis=3)), axis=-1)
    eval_generator.X = np.concatenate((np.expand_dims(eeg_eval_gen.X,axis=3),
                                        np.expand_dims(eog_eval_gen.X,axis=3)), axis=-1)
else: # num_channel == 3
    train_generator.X = np.concatenate((np.expand_dims(eeg_train_gen.X,axis=3),
                                        np.expand_dims(eog_train_gen.X,axis=3),
                                        np.expand_dims(emg_train_gen.X,axis=3)), axis=-1)
    test_generator.X = np.concatenate((np.expand_dims(eeg_test_gen.X,axis=3),
                                        np.expand_dims(eog_test_gen.X,axis=3),
                                        np.expand_dims(emg_test_gen.X,axis=3)), axis=-1)
    eval_generator.X = np.concatenate((np.expand_dims(eeg_eval_gen.X,axis=3),
                                        np.expand_dims(eog_eval_gen.X,axis=3),
                                       np.expand_dims(emg_eval_gen.X,axis=3)), axis=-1)
train_generator.y = eeg_train_gen.y
train_generator.label = eeg_train_gen.label
test_generator.y = eeg_test_gen.y
test_generator.label = eeg_test_gen.label
eval_generator.y = eeg_eval_gen.y
eval_generator.label = eeg_eval_gen.label

# clear individual data
del eeg_train_gen
del eeg_test_gen
del eeg_eval_gen
if (eog_active):
    del eog_train_gen
    del eog_test_gen
    del eog_eval_gen
if (emg_active):
    del emg_train_gen
    del emg_test_gen
    del emg_eval_gen

# generate index here
train_generator.indexing()
test_generator.indexing()
eval_generator.indexing()
# shuffle training data
train_generator.shuffle_data()

train_batches_per_epoch = np.floor(train_generator.data_size / config.batch_size).astype(np.int16)
eval_batches_per_epoch = np.floor(eval_generator.data_size / config.batch_size).astype(np.int16)
test_batches_per_epoch = np.floor(test_generator.data_size / config.batch_size).astype(np.int16)

print("Train/Test set: {:d}/{:d}".format(train_generator.data_size, test_generator.data_size))

# variable to keep track of best fscore
best_fscore = 0.0
best_acc = 0.0
best_kappa = 0.0
# Training
# ==================================================

with tf.Graph().as_default():
    session_conf = tf.ConfigProto(
      allow_soft_placement=FLAGS.allow_soft_placement,
      log_device_placement=FLAGS.log_device_placement)
    sess = tf.Session(config=session_conf)
    with sess.as_default():
        cnn = CNN_Sleep(config=config)

        # Define Training procedure
        global_step = tf.Variable(0, name="global_step", trainable=False)
        optimizer = tf.train.AdamOptimizer(config.learning_rate)
        grads_and_vars = optimizer.compute_gradients(cnn.loss)
        train_op = optimizer.apply_gradients(grads_and_vars, global_step=global_step)

        out_dir = os.path.abspath(os.path.join(os.path.curdir,FLAGS.out_dir))
        print("Writing to {}\n".format(out_dir))

        saver = tf.train.Saver(tf.all_variables(),max_to_keep=1)

        # initialize all variables
        print("Model initialized")
        sess.run(tf.initialize_all_variables())

        def train_step(x_batch, y_batch):
            """
            A single training step
            """
            feed_dict = {
                cnn.X: x_batch,
                cnn.Y: y_batch,
                cnn.dropout_keep_prob: config.dropout_keep_prob,
                cnn.dropout_keep_prob_conv: config.dropout_keep_prob_conv
            }
            _, step, loss, acc = sess.run(
               [train_op, global_step, cnn.loss, cnn.accuracy],
               feed_dict)
            return step, loss, acc

        def dev_step(x_batch, y_batch):
            feed_dict = {
                cnn.X: x_batch,
                cnn.Y: y_batch,
                cnn.dropout_keep_prob: 1.0,
                cnn.dropout_keep_prob_conv: 1.0
            }
            _, loss, yhat, score, acc = sess.run(
                [global_step, cnn.loss, cnn.pred_Y, cnn.score, cnn.accuracy],
                feed_dict)
            return acc, yhat, score

        start_time = time.time()

        # Loop over number of epochs
        for epoch in range(config.training_epoch):
            print("{} Epoch number: {}".format(datetime.now(), epoch + 1))

            train_loss_epoch = 0.0
            step = 1
            while step < train_batches_per_epoch:
                # Get a batch
                x_batch, y_batch, label_batch = train_generator.next_batch(config.batch_size_per_class)
                train_step_, train_loss_, train_acc_ = train_step(x_batch, y_batch)
                time_str = datetime.now().isoformat()
                print("{}: step {}, loss {}, accuracy {}".format(time_str, train_step_, train_loss_, train_acc_))

                train_loss_epoch += train_loss_
                step += 1

                current_step = tf.train.global_step(sess, global_step)
                if current_step % config.evaluate_every == 0:

                    test_yhat = np.zeros_like(test_generator.label)
                    test_step = 1
                    while test_step < test_batches_per_epoch:
                        x_batch, y_batch, _ = test_generator.next_batch(config.batch_size)
                        _, test_yhat_, _ = dev_step(x_batch, y_batch)
                        test_yhat[(test_step-1)*config.batch_size : test_step*config.batch_size] = test_yhat_
                        test_step += 1
                    if(test_generator.pointer < test_generator.data_size):
                        actual_len, x_batch, y_batch, _ = test_generator.rest_batch(config.batch_size)
                        _, test_yhat_, _ = dev_step(x_batch, y_batch)
                        test_yhat[(test_step-1)*config.batch_size : test_generator.data_size] = test_yhat_
                    test_fscore = f1_score(test_generator.label, test_yhat + 1, average='macro')
                    test_acc = accuracy_score(test_generator.label, test_yhat + 1)
                    test_kappa = cohen_kappa_score(test_generator.label, test_yhat + 1)

                    eval_yhat = np.zeros_like(eval_generator.label)
                    eval_step = 1
                    while eval_step < eval_batches_per_epoch:
                        x_batch, y_batch, _ = eval_generator.next_batch(config.batch_size)
                        _, eval_yhat_, _ = dev_step(x_batch, y_batch)
                        eval_yhat[(eval_step-1)*config.batch_size : eval_step*config.batch_size] = eval_yhat_
                        eval_step += 1
                    if(eval_generator.pointer < eval_generator.data_size):
                        actual_len, x_batch, y_batch, _ = eval_generator.rest_batch(config.batch_size)
                        _, eval_yhat_, _ = dev_step(x_batch, y_batch)
                        eval_yhat[(eval_step-1)*config.batch_size : eval_generator.data_size] = eval_yhat_
                    eval_fscore = f1_score(eval_generator.label, eval_yhat + 1, average='macro')
                    eval_acc = accuracy_score(eval_generator.label, eval_yhat + 1)
                    eval_kappa = cohen_kappa_score(eval_generator.label, eval_yhat + 1)

                    print("{:g} {:g} {:g} {:g} {:g} {:g}".format(eval_acc, eval_fscore, eval_kappa, test_acc, test_fscore,  test_kappa))
                    with open(os.path.join(out_dir, "result_log.txt"), "a") as text_file:
                        text_file.write("{:g} {:g} {:g} {:g} {:g} {:g}\n".format(eval_acc, eval_fscore, eval_kappa, test_acc, test_fscore,  test_kappa))

                    if(eval_acc > best_acc):
                        best_acc = eval_acc

                        checkpoint_name = os.path.join(checkpoint_path, 'model_step' + str(current_step) +'.ckpt')
                        save_path = saver.save(sess, checkpoint_name)

                        print("Best model updated")
                        source_file = checkpoint_name
                        dest_file = os.path.join(checkpoint_path, 'best_model_acc')
                        shutil.copy(source_file + '.data-00000-of-00001', dest_file + '.data-00000-of-00001')
                        shutil.copy(source_file + '.index', dest_file + '.index')
                        shutil.copy(source_file + '.meta', dest_file + '.meta')

                    # Reset the file pointer of the data generators
                    test_generator.reset_pointer()
                    eval_generator.reset_pointer()
            train_generator.reset_pointer()
        end_time = time.time()
        with open(os.path.join(out_dir, "training_time.txt"), "a") as text_file:
            text_file.write("{:g}\n".format((end_time - start_time)))
