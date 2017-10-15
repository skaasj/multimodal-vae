from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import torch
from torch.autograd import Variable
from torchvision.utils import save_image

from model import load_checkpoint


if __name__ == "__main__":
    import os
    import argparse
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    parser.add_argument('n_samples', type=int, 
                        help='Number of images and texts to sample.')
    # TODO:
    # parser.add_argument('--condition_on_images', action='store_true',
    #                     help='If True, generate text conditioned on images.')
    # parser.add_argument('--condition_on_text', action='store_true',
    #                     help='If True, generate images conditioned on text.')
    parser.add_argument('--cuda', action='store_true', default=False,
                        help='enables CUDA training')
    args.cuda = args.cuda and torch.cuda.is_available()

    # load trained model
    vae = load_checkpoint('./trained_models/model_best.pth.tar', use_cuda=args.cuda)

    # sample from gaussian distribution
    sample = Variable(torch.randn(args.n_samples, 20))
    if args.cuda:
        sample = sample.cuda()
    
    # generate image and text
    image_recon = vae.decoder_image(sample).cpu()
    text_recon = vae.decoder_text(sample).cpu()

    if not os.path.isdir('./results'):
        os.mkdirs('./results')

    # save image samples to filesystem
    save_image(image_recon.data.view(args.n_samples, 1, 28, 28),
               './results/sample_image.png')

    # save text samples to filesystem
    with open('./results/sample_texts.txt', 'w') as fp:
        text_recon_np = text_recon.data.numpy().tolist():
        for item in text_recon_np:
            fp.write('%s\n' % item)
