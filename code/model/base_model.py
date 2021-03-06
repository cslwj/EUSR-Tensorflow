import tensorflow as tf
import os, math

class BaseModel:
    def __init__(self, args):
        self.args = args
        self.init_global_step()
        self.ckpt_dir = os.path.join(self.args.exp_dir, self.args.exp_name)

    def conv(self, x, num_feats, kernel_size=[3,3], activation=None, kernel_initializer=None):
        if self.args.is_init_res:
            scale_list = list(map(lambda x: int(x), self.args.scale.split('+')))
            num_up = self.args.num_res + self.args.num_res_up * 4 * int(math.log(int(max(scale_list)), 2))
            kernel_initializer=tf.contrib.layers.variance_scaling_initializer(factor=0.0001/num_up, mode="FAN_IN", uniform=False)
        elif self.args.is_init_he:
            kernel_initializer=tf.contrib.layers.variance_scaling_initializer()
        return tf.layers.conv2d(x, num_feats, kernel_size, padding='same', activation=activation, kernel_initializer=kernel_initializer)

    def conv_xavier(self, x, num_feats, kernel_size, activation=None):
        return tf.layers.conv2d(x, num_feats, kernel_size, padding='same', activation=activation)

    def res_block(self, x, num_feats, kernel_size, scale=1):
        tmp = self.conv(x, num_feats, kernel_size, activation=tf.nn.relu)
        tmp = self.conv(tmp, num_feats, kernel_size)
        tmp *= scale
        return x + tmp
       
    def res_module(self, x, num_feats, num_res):
        before_res = x
        for _ in range(num_res):
            x = self.res_block(x, num_feats, [3,3])
        x = self.conv_xavier(x, num_feats, [3,3])
        return before_res + x

    def mean_shift(self, x, is_add=False):
        mean_vec = [0.4488, 0.4371, 0.4040]
        mean_vec = [x * 255 for x in mean_vec] 
        if is_add:
            x = x + mean_vec
        else:
            x = x - mean_vec
        return x

    def scale_specific_module(self, x, num_feats, kernel_size=[5,5]):
        x = self.res_block(x, num_feats, kernel_size)
        x = self.res_block(x, num_feats, kernel_size)
        return x

    def scale_specific_upsampler(self, x, scale):
        x = self.upsampler(x, scale)
        x = self.conv_xavier(x, self.args.num_channels, [3,3])
        return x

    # Method to upscale an image using conv2d transpose.
    def upsampler(self, x, scale):
        if (scale & (scale - 1)) == 0:
            for _ in range(int(math.log(scale, 2))):
                x_list = list()
                for _ in range(4):
                    x = self.res_module(x, self.args.num_feats, self.args.num_res_up)
                    x_list.append(x)
                x = tf.concat(x_list, axis=3)
                x = tf.depth_to_space(x, 2)
            return x 
        else:
            raise NotImplementedError              

    # save function thet save the checkpoint in the path defined in argsfile
    def save(self, sess):
        print("Saving model...")
        self.saver.save(sess, self.ckpt_dir+"/model.ckpt", self.global_step)
        print("Model saved")

    # load lateset checkpoint from the experiment path defined in args_file
    def load(self, sess):
        latest_checkpoint = tf.train.latest_checkpoint(self.ckpt_dir)
        if self.args.ckpt_name:
            ckpt = self.ckpt_dir+"/"+self.args.ckpt_name
        else:
            ckpt = latest_checkpoint
        print("Loading model checkpoint {} ...\n".format(ckpt))
        self.saver.restore(sess, ckpt)
        print("Model loaded")

    # just inialize a tensorflow variable to use it as global step counter
    def init_global_step(self):
        # DON'T forget to add the global step tensor to the tensorflow trainer
        with tf.variable_scope('global_step'):
            self.global_step = tf.Variable(0, trainable=False, name='global_step')

    def init_saver(self):
        self.saver = tf.train.Saver(max_to_keep=self.args.max_to_keep)

    def count_num_trainable_params(self):
        tot_nb_params = 0
        for trainable_variable in tf.trainable_variables():
            shape = trainable_variable.get_shape() # e.g [D,F] or [W,H,C]
            current_nb_params = self.get_num_params_shape(shape)
            tot_nb_params = tot_nb_params + current_nb_params
        return tot_nb_params

    def get_num_params_shape(self, shape):
        nb_params = 1
        for dim in shape:
            nb_params = nb_params*int(dim)
        return nb_params 

