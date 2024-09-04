# Copyright (c) 2021 Mobvoi Inc. (authors: Binbin Zhang
#               2023    SRIBD              Shuai Wang )
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import io
import logging
import multiprocessing
import os
import random
import tarfile
import time
import sys

AUDIO_FORMAT_SETS = {'flac', 'mp3', 'm4a', 'ogg', 'opus', 'wav', 'wma'}


def write_tar_file(data_list, tar_file, index=0, total=1):
    logging.info('Processing {} {}/{}'.format(tar_file, index, total))
    read_time = 0.0
    write_time = 0.0
    with tarfile.open(tar_file, "w") as tar:
        for item in data_list:
            assert len(
                item) == 3, 'item should have 3 elements: Key, Speaker, Wav'
            key, spks, wavs = item
            spk_idx = 1
            for spk in spks:
                assert isinstance(spk, str)
                spk_file = key + '.spk' + str(spk_idx)
                spk = spk.encode('utf8')
                spk_data = io.BytesIO(spk)
                spk_info = tarfile.TarInfo(spk_file)
                spk_info.size = len(spk)
                tar.addfile(spk_info, spk_data)
                spk_idx = spk_idx + 1

            spk_idx = 0
            for wav in wavs:
                suffix = wav.split('.')[-1]
                assert suffix in AUDIO_FORMAT_SETS
                ts = time.time()
                try:
                    with open(wav, 'rb') as fin:
                        data = fin.read()
                except FileNotFoundError as e:
                    print(e)
                    sys.exit()
                read_time += (time.time() - ts)
                ts = time.time()
                if spk_idx > 0:
                    wav_file = key + '_spk' + str(spk_idx) + '.' + suffix
                else:
                    wav_file = key + '.' + suffix
                wav_data = io.BytesIO(data)
                wav_info = tarfile.TarInfo(wav_file)
                wav_info.size = len(data)
                tar.addfile(wav_info, wav_data)
                write_time += (time.time() - ts)
                spk_idx = spk_idx + 1

        logging.info('read {} write {}'.format(read_time, write_time))


def get_args():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--num_utts_per_shard',
                        type=int,
                        default=1000,
                        help='num utts per shard')
    parser.add_argument('--num_threads',
                        type=int,
                        default=1,
                        help='num threads for make shards')
    parser.add_argument('--prefix',
                        default='shards',
                        help='prefix of shards tar file')
    parser.add_argument('--seed', type=int, default=42, help='random seed')
    parser.add_argument('--shuffle',
                        action='store_true',
                        help='whether to shuffle data')
    parser.add_argument('wav_file', help='wav file')
    parser.add_argument('utt2spk_file', help='utt2spk file')
    parser.add_argument('shards_dir', help='output shards dir')
    parser.add_argument('shards_list', help='output shards list file')
    args = parser.parse_args()
    return args


def main():
    args = get_args()
    random.seed(args.seed)
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')

    wav_table = {}
    with open(args.wav_file, 'r', encoding='utf8') as fin:
        for line in fin:
            arr = line.strip().split()
            key = arr[0]  # key = os.path.splitext(arr[0])[0]
            wav_table[key] = [arr[i + 1] for i in range(len(arr) - 1)]

    data = []
    with open(args.utt2spk_file, 'r', encoding='utf8') as fin:
        for line in fin:
            arr = line.strip().split()
            key = arr[0]  # key = os.path.splitext(arr[0])[0]
            spks = [arr[i + 1] for i in range(len(arr) - 1)]
            assert key in wav_table
            wavs = wav_table[key]
            data.append((key, spks, wavs))

    if args.shuffle:
        random.shuffle(data)

    num = args.num_utts_per_shard
    chunks = [data[i:i + num] for i in range(0, len(data), num)]
    os.makedirs(args.shards_dir, exist_ok=True)

    # Using thread pool to speedup
    pool = multiprocessing.Pool(processes=args.num_threads)
    shards_list = []
    num_chunks = len(chunks)
    for i, chunk in enumerate(chunks):
        tar_file = os.path.join(args.shards_dir,
                                '{}_{:09d}.tar'.format(args.prefix, i))
        shards_list.append(tar_file)
        pool.apply_async(write_tar_file, (chunk, tar_file, i, num_chunks))

    pool.close()
    pool.join()

    with open(args.shards_list, 'w', encoding='utf8') as fout:
        for name in shards_list:
            fout.write(name + '\n')


if __name__ == '__main__':
    main()
