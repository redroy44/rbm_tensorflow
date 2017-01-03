# -*- coding: utf-8 -*-
"""
Created on Tue Jan  3 10:50:39 2017

@author: pbandurs
"""
import time
import numpy as np
import tensorflow as tf
from tensorflow.examples.tutorials.mnist import input_data

class RBM(object):
    """ Restricted Bolzmann Machine """
    def __init__(
        self,
        sess,
        data,
        n_visible=784,
        n_hidden=500,
        k=15,
        image_width=28,
        y_dim=10,
        batch_size=64,
        W=None,
        hbias=None,
        vbias=None):

        """
        RBM constructor. Defines the parameters of the model along with
        basic operations for inferring hidden from visible (and vice-versa),
        as well as for performing CD updates.

        :param input: None for standalone RBMs or symbolic variable if RBM is
        part of a larger graph.

        :param n_visible: number of visible units

        :param n_hidden: number of hidden units

        :param W: None for standalone RBMs or symbolic variable pointing to a
        shared weight matrix in case RBM is part of a DBN network; in a DBN,
        the weights are shared between RBMs and layers of a MLP

        :param hbias: None for standalone RBMs or symbolic variable pointing
        to a shared hidden units bias vector in case RBM is part of a
        different network

        :param vbias: None for standalone RBMs or a symbolic variable
        pointing to a shared visible units bias
        """

        self.data = data
        self.sess = sess
        self.n_visible = n_visible
        self.n_hidden = n_hidden
        self.image_width = image_width
        self.y_dim = y_dim
        self.k = k
        self.batch_size = batch_size

        tf.set_random_seed(1234)

        abs_val = -4*np.sqrt(6./(self.n_hidden + self.n_visible))
        self.W = tf.get_variable("W", [self.n_visible, self.n_hidden], tf.float32,
                            tf.random_uniform_initializer(minval=-abs_val, maxval=abs_val))
        self.hbias = tf.get_variable("hbias", [self.n_hidden, 1], tf.float32,
                                 tf.constant_initializer(0.0))
        self.vbias = tf.get_variable("vbias", [self.n_visible, 1], tf.float32,
                                 tf.constant_initializer(0.0))

        # **** WARNING: It is not a good idea to put things in this list
        # other than shared variables created in this function.
        #self.params = [self.W, self.hbias, self.vbias]
        
        self.build_model()
        
    def build_model(self):
        self.input = tf.placeholder(tf.float32, [self.batch_size, 784],
                                     name='real_images')
        
        self.loss = self.get_cost_updates(input=self.input, k=self.k)
        
        #self.saver = tf.train.Saver()

    def train(self):
        data_X = self.data.images
        print (tf.shape(data_X))
        optim = tf.train.GradientDescentOptimizer(0.1)\
            .minimize(self.loss)
        
        tf.global_variables_initializer().run()
        
        counter = 1
        start_time = time.time()
        
        for epoch in range(20):
            batch_idxs = len(data_X) // self.batch_size

            for idx in range(0, batch_idxs):
                batch_images = data_X[idx*self.batch_size:(idx+1)*self.batch_size]
                #batch_labels = data_y[idx*self.batch_size:(idx+1)*self.batch_size]

                _ = self.sess.run([optim], feed_dict={self.input: batch_images})
                loss = self.loss.eval({self.input: batch_images})

                counter += 1
                print("Epoch: [%2d] [%4d/%4d] time: %4.4f, loss: %.8f" \
                    % (epoch, idx, batch_idxs, time.time() - start_time, loss))
                
    def sample(self):
        pass
        
    def sample_prob(self, probs):
        return tf.nn.relu(tf.sign(probs - tf.random_uniform(tf.shape(probs))))

    def free_energy(self, v_sample):
        ''' Function to compute the free energy '''
        flat_v = tf.reshape(v_sample, [self.batch_size, -1])
        
        wx_b = tf.add(tf.matmul(flat_v, self.W), tf.transpose(self.hbias))
        vbias_term = tf.matmul(flat_v, self.vbias)
        hidden_term = tf.reduce_sum(tf.log(1 + tf.exp(wx_b)), axis=1)
        return -hidden_term - vbias_term

    def propup(self, vis):
        '''This function propagates the visible units activation upwards to
        the hidden units

        Note that we return also the pre-sigmoid activation of the
        layer. As it will turn out later, due to how Theano deals with
        optimizations, this symbolic variable will be needed to write
        down a more stable computational graph (see details in the
        reconstruction cost function)

        '''
        pre_sigmoid_activation = tf.add(tf.matmul(vis, self.W), tf.transpose(self.hbias))
        return [pre_sigmoid_activation, tf.nn.sigmoid(pre_sigmoid_activation)]

    def sample_h_given_v(self, v0_sample):
        ''' This function infers state of hidden units given visible units '''
        # compute the activation of the hidden units given a sample of
        # the visibles
        pre_sigmoid_h1, h1_mean = self.propup(v0_sample)
        # get a sample of the hiddens given their activation
        # Note that theano_rng.binomial returns a symbolic sample of dtype
        # int64 by default. If we want to keep our computations in floatX
        # for the GPU we need to specify to return the dtype floatX
        h1_sample = self.sample_prob(h1_mean)
        return [pre_sigmoid_h1, h1_mean, h1_sample]

    def propdown(self, hid):
        '''This function propagates the hidden units activation downwards to
        the visible units

        Note that we return also the pre_sigmoid_activation of the
        layer. As it will turn out later, due to how Theano deals with
        optimizations, this symbolic variable will be needed to write
        down a more stable computational graph (see details in the
        reconstruction cost function)

        '''
        pre_sigmoid_activation = tf.add(tf.matmul(hid, tf.transpose(self.W)), tf.transpose(self.vbias))
        return [pre_sigmoid_activation, tf.nn.sigmoid(pre_sigmoid_activation)]

    def sample_v_given_h(self, h0_sample):
        ''' This function infers state of visible units given hidden units '''
        # compute the activation of the visible given the hidden sample
        pre_sigmoid_v1, v1_mean = self.propdown(h0_sample)
        # get a sample of the visible given their activation
        # Note that theano_rng.binomial returns a symbolic sample of dtype
        # int64 by default. If we want to keep our computations in floatX
        # for the GPU we need to specify to return the dtype floatX
        v1_sample = self.sample_prob(v1_mean)
        return [pre_sigmoid_v1, v1_mean, v1_sample]

    def gibbs_hvh(self, h0_sample):
        ''' This function implements one step of Gibbs sampling,
            starting from the hidden state'''
        pre_sigmoid_v1, v1_mean, v1_sample = self.sample_v_given_h(h0_sample)
        pre_sigmoid_h1, h1_mean, h1_sample = self.sample_h_given_v(v1_sample)
        return [pre_sigmoid_v1, v1_mean, v1_sample,
                pre_sigmoid_h1, h1_mean, h1_sample]

    def gibbs_vhv(self, v0_sample):
        ''' This function implements one step of Gibbs sampling,
            starting from the visible state'''
        pre_sigmoid_h1, h1_mean, h1_sample = self.sample_h_given_v(v0_sample)
        pre_sigmoid_v1, v1_mean, v1_sample = self.sample_v_given_h(h1_sample)
        return [pre_sigmoid_h1, h1_mean, h1_sample,
                pre_sigmoid_v1, v1_mean, v1_sample]
                
    def get_cost_updates(self, input, k=1):
        """This functions implements one step of CD-k or PCD-k

        :param lr: learning rate used to train the RBM

        :param persistent: None for CD. For PCD, shared variable
            containing old state of Gibbs chain. This must be a shared
            variable of size (batch size, number of hidden units).

        :param k: number of Gibbs steps to do in CD-k/PCD-k

        Returns a proxy for the cost and the updates dictionary. The
        dictionary contains the update rules for weights and biases but
        also an update of the shared variable used to store the persistent
        chain, if one is used.

        """
        # compute positive phase
        pre_sigmoid_ph, ph_mean, ph_sample = self.sample_h_given_v(input)
        
        # decide how to initialize persistent chain:
        # for CD, we use the newly generate hidden sample
        chain_start = ph_sample
        
        # perform actual negative phase
        for k in range(k):
            [ pre_sigmoid_nvs, nv_mean, nv_sample,
            pre_sigmoid_nh, nh_mean, chain_start ] = self.gibbs_hvh(chain_start)

        chain_end = nv_sample
        
        # CD-k loss
        loss = tf.reduce_mean(self.free_energy(input)) \
            - tf.reduce_mean(self.free_energy(chain_end))
            
        return loss
        

mnist = input_data.read_data_sets("MNIST_data/", one_hot=True)

with tf.Session() as sess:
    rbm = RBM(sess, mnist.train)
    rbm.train()
    
