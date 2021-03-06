from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import torch
from torch.autograd import Variable
from torchvision import transforms, datasets

from train_imageonly import load_checkpoint
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE


if __name__ == "__main__":
    import os
    import pickle
    import argparse
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm

    parser = argparse.ArgumentParser()
    parser.add_argument('model_path', type=str, help='path to trained model file')
    parser.add_argument('--pca_only', action='store_true', default=False)
    parser.add_argument('--cuda', action='store_true', default=False,
                        help='enables CUDA training')
    args = parser.parse_args()
    args.cuda = args.cuda and torch.cuda.is_available()

    # use this instead of shuffle loader because we don't want 
    # to have negative examples here.
    loader = torch.utils.data.DataLoader(
        datasets.MNIST('../data', train=False, download=True, 
                       transform=transforms.ToTensor()),
        batch_size=128, shuffle=True)

    vae = load_checkpoint(args.model_path, use_cuda=args.cuda)
    vae.eval()
    if args.cuda:
        vae.cuda()

    for batch_idx, (image, text) in enumerate(loader):
        if args.cuda:
            image, text = image.cuda(), text.cuda()
        image, text = Variable(image, volatile=True), Variable(text, volatile=True)
        image = image.view(-1, 784)  # flatten image

        mu, logvar = vae.encode(image)
        z = vae.reparameterize(mu, logvar)
        
        if batch_idx == 0:
            latents = z
            labels = text
        else:
            latents = torch.cat((latents, z))
            labels = torch.cat((labels, text))

    latents = latents.cpu().data.numpy()
    labels = labels.cpu().data.numpy()

    with open('./results/dump.pkl', 'wb') as fp:
        pickle.dump({'latents': latents, 'labels': labels}, fp)

    if args.pca_only:
        pca_2 = PCA(n_components=2)
        latents = pca_2.fit_transform(latents)
    else:
        # > 50 dimensions is too expensive for tSNE
        if latents.shape[1] > 50:  
            pca_50 = PCA(n_components=50)
            latents = pca_50.fit_transform(latents)
        tsne = TSNE(n_components=2, verbose=1, perplexity=40, n_iter=300)
        latents = tsne.fit_transform(latents)

    # now we have latents guaranteed to be 2 dimensions
    # let's plot the manifold
    colors = iter(cm.rainbow(np.linspace(0, 1, 10)))  # ten kinds of colors

    plt.figure()
    for i in xrange(10):
        latents_i = latents[labels == i]
        plt.scatter(latents_i[:, 0], latents_i[:, 1], color=next(colors), 
                    label=str(i), alpha=0.3, edgecolors='none')
    plt.legend()
    if not os.path.exists('./results'):
        os.makedirs('./results')
    plt.savefig('./results/manifold.png')
