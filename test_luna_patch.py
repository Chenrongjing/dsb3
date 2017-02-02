import string
import sys
import lasagne as nn
import numpy as np
import theano
import buffering
import pathfinder
import utils
from configuration import config, set_configuration
from utils_plots import plot_slice_3d_3
import theano.tensor as T

theano.config.warn_float64 = 'raise'

if len(sys.argv) < 2:
    sys.exit("Usage: train.py <configuration_name>")

config_name = sys.argv[1]
set_configuration(config_name)

# metadata
metadata_dir = utils.get_dir_path('models', pathfinder.METADATA_PATH)
metadata_path = utils.find_model_metadata(metadata_dir, config_name)

metadata = utils.load_pkl(metadata_path)
expid = metadata['experiment_id']

# predictions path
predictions_dir = utils.get_dir_path('model-predictions', pathfinder.METADATA_PATH)
outputs_path = predictions_dir + '/' + expid
utils.auto_make_dir(outputs_path)

print 'Build model'
model = config().build_model()
all_layers = nn.layers.get_all_layers(model.l_out)
all_params = nn.layers.get_all_params(model.l_out)
num_params = nn.layers.count_params(model.l_out)
print '  number of parameters: %d' % num_params
print string.ljust('  layer output shapes:', 36),
print string.ljust('#params:', 10),
print 'output shape:'
for layer in all_layers:
    name = string.ljust(layer.__class__.__name__, 32)
    num_param = sum([np.prod(p.get_value().shape) for p in layer.get_params()])
    num_param = string.ljust(num_param.__str__(), 10)
    print '    %s %s %s' % (name, num_param, layer.output_shape)

nn.layers.set_all_param_values(model.l_out, metadata['param_values'])

valid_loss = config().build_objective(model, deterministic=True)

x_shared = nn.utils.shared_empty(dim=len(model.l_in.shape))
y_shared = nn.utils.shared_empty(dim=len(model.l_target.shape))

givens_valid = {}
givens_valid[model.l_in.input_var] = x_shared
givens_valid[model.l_target.input_var] = y_shared

# theano functions
iter_get_predictions = theano.function([], nn.layers.get_output(model.l_out), givens=givens_valid,
                                       on_unused_input='ignore')
iter_get_targets = theano.function([], nn.layers.get_output(model.l_target), givens=givens_valid,
                                   on_unused_input='ignore')
iter_get_inputs = theano.function([], nn.layers.get_output(model.l_in), givens=givens_valid,
                                  on_unused_input='ignore')
iter_validate = theano.function([], valid_loss, givens=givens_valid)

valid_data_iterator = config().valid_data_iterator

print
print 'Data'
print 'n validation: %d' % valid_data_iterator.nsamples

valid_losses = []
for n, (x_chunk_train, y_chunk_train, id_train) in enumerate(
        buffering.buffered_gen_threaded(valid_data_iterator.generate())):
    # load chunk to GPU
    x_shared.set_value(x_chunk_train)
    y_shared.set_value(y_chunk_train)

    loss = iter_validate()
    print n, loss
    valid_losses.append(loss)
    pp = iter_get_predictions()
    tt = iter_get_targets()
    ii = iter_get_inputs()

    for k in xrange(pp.shape[0]):
        try:
            plot_slice_3d_3(input=ii[k, 0], mask=tt[k, 0], prediction=pp[k, 0],
                            axis=0, pid='-'.join([str(n), str(k), str(id_train[k])]),
                            img_dir=outputs_path)
        except:
            print 'no plot'

print 'Validation loss', np.mean(valid_losses)