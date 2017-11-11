"""Download the Librispeech dataset
http://www.openslr.org/12/
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import wget
import shutil
import tarfile
import subprocess

import io
import fnmatch
from tpdm import tqdm


LIBRI_SPEECH_URLS = {
    "train": ["http://www.openslr.org/resources/12/train-clean-100.tar.gz",
              "http://www.openslr.org/resources/12/train-clean-360.tar.gz",
              "http://www.openslr.org/resources/12/train-other-500.tar.gz"],

    "val": ["http://www.openslr.org/resources/12/dev-clean.tar.gz",
            "http://www.openslr.org/resources/12/dev-other.tar.gz"],

    "test": ["http://www.openslr.org/resources/12/test-clean.tar.gz",
             "http://www.openslr.org/resources/12/test-other.tar.gz"]
}


def create_manifest(data_path, tag, ordered=True):
    manifest_path = '%s_manifest.csv' % tag
    file_paths = []
    wav_files = [os.path.join(dirpath, f)
                 for dirpath, dirnames, files in os.walk(data_path)
                 for f in fnmatch.filter(files, '*.wav')]
    for file_path in tqdm(wav_files, total=len(wav_files)):
        file_paths.append(file_path.strip())
    print('\n')
    if ordered:
        _order_files(file_paths)
    with io.FileIO(manifest_path, "w") as file:
        for wav_path in tqdm(file_paths, total=len(file_paths)):
            transcript_path = wav_path.replace('/wav/', '/txt/').replace('.wav', '.txt')
            sample = os.path.abspath(wav_path) + ',' + os.path.abspath(transcript_path) + '\n'
            file.write(sample.encode('utf-8'))
    print('\n')


def _order_files(file_paths):
    print("Sorting files by length...")

    def func(element):
        output = subprocess.check_output(
            ['soxi -D \"%s\"' % element.strip()],
            shell=True
        )
        return float(output)

    file_paths.sort(key=func)



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Processes and downloads LibriSpeech dataset.')
    parser.add_argument("--target_dir", default='LibriSpeech_dataset/', type=str, help="Directory to store the dataset.")
    parser.add_argument('--sample_rate', default=16000, type=int, help='Sample rate')
    parser.add_argument('--files_to_use', default="train-clean-100.tar.gz,"
                                                  "train-clean-360.tar.gz,train-other-500.tar.gz,"
                                                  "dev-clean.tar.gz,dev-other.tar.gz,"
                                                  "test-clean.tar.gz,test-other.tar.gz", type=str,
                        help='list of file names to download')
    args = parser.parse_args()

    def _preprocess_transcript(phrase):
        return phrase.strip().upper()


    def _process_file(wav_dir, txt_dir, base_filename, root_dir):
        full_recording_path = os.path.join(root_dir, base_filename)
        assert os.path.exists(full_recording_path) and os.path.exists(root_dir)
        wav_recording_path = os.path.join(wav_dir, base_filename.replace(".flac", ".wav"))
        subprocess.call(["sox {}  -r {} -b 16 -c 1 {}".format(full_recording_path, str(args.sample_rate),
                                                              wav_recording_path)], shell=True)
        # process transcript
        txt_transcript_path = os.path.join(txt_dir, base_filename.replace(".flac", ".txt"))
        transcript_file = os.path.join(root_dir, "-".join(base_filename.split('-')[:-1]) + ".trans.txt")
        assert os.path.exists(transcript_file), "Transcript file {} does not exist.".format(transcript_file)
        transcriptions = open(transcript_file).read().strip().split("\n")
        transcriptions = {t.split()[0].split("-")[-1]: " ".join(t.split()[1:]) for t in transcriptions}
        with open(txt_transcript_path, "w") as f:
            key = base_filename.replace(".flac", "").split("-")[-1]
            assert key in transcriptions, "{} is not in the transcriptions".format(key)
            f.write(_preprocess_transcript(transcriptions[key]))
            f.flush()


    def download():
        target_dl_dir = args.target_dir
        if not os.path.exists(target_dl_dir):
            os.makedirs(target_dl_dir)
        files_to_dl = args.files_to_use.strip().split(',')
        for split_type, lst_libri_urls in LIBRI_SPEECH_URLS.items():
            split_dir = os.path.join(target_dl_dir, split_type)
            if not os.path.exists(split_dir):
                os.makedirs(split_dir)
            split_wav_dir = os.path.join(split_dir, "wav")
            if not os.path.exists(split_wav_dir):
                os.makedirs(split_wav_dir)
            split_txt_dir = os.path.join(split_dir, "txt")
            if not os.path.exists(split_txt_dir):
                os.makedirs(split_txt_dir)
            extracted_dir = os.path.join(split_dir, "LibriSpeech")
            if os.path.exists(extracted_dir):
                shutil.rmtree(extracted_dir)
            for url in lst_libri_urls:
                # check if we want to dl this file
                dl_flag = False
                for f in files_to_dl:
                    if url.find(f) != -1:
                        dl_flag = True
                if not dl_flag:
                    print("Skipping url: {}".format(url))
                    continue
                filename = url.split("/")[-1]
                target_filename = os.path.join(split_dir, filename)
                if not os.path.exists(target_filename):
                    wget.download(url, split_dir)
                print("Unpacking {}...".format(filename))
                tar = tarfile.open(target_filename)
                tar.extractall(split_dir)
                tar.close()
                os.remove(target_filename)
                print("Converting flac files to wav and extracting transcripts...")
                assert os.path.exists(extracted_dir), "Archive {} was not properly uncompressed.".format(filename)
                for root, subdirs, files in os.walk(extracted_dir):
                    for f in files:
                        if f.find(".flac") != -1:
                            _process_file(wav_dir=split_wav_dir, txt_dir=split_txt_dir,
                                          base_filename=f, root_dir=root)

                print("Finished {}".format(url))
                shutil.rmtree(extracted_dir)
            create_manifest(split_dir, 'libri_' + split_type)


    download()
