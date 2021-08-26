# -*- coding: utf-8 -*-
# @Time    : 7/5/21 5:23 PM
# @Author  : Jingnan
# @Email   : jiajingnan2222@gmail.com
import torch
import datetime
import os
import shutil
import time
from ssc_scoring.mymodules.path import PathInit, PathScoreInit, PathPosInit, PathPos

import myutil.myutil as futil
import numpy as np
import nvidia_smi
import pandas as pd
from filelock import FileLock

from ssc_scoring.mymodules.confusion_test import confusion
# from ssc_scoring.mymodules.path import PathPos as Path
# from mymodules.set_args_pos import args
from torch.utils.data import WeightedRandomSampler

def sampler_by_disext(tr_y, sys_ratio=0.8):
    """Balanced sampler according to score distribution of disext.

    Args:
        tr_y:
        sys_ratio:

    Returns:

    """
    disext_list = []
    for sample in tr_y:
        if type(sample) in [list, np.ndarray]:
            disext_list.append(sample[0])
        else:
            disext_list.append(sample)
    disext_np = np.array(disext_list)
    disext_unique = np.unique(disext_np)
    disext_unique_list = list(disext_unique)

    class_sample_count = np.array([len(np.where(disext_np == t)[0]) for t in disext_unique])
    if sys_ratio:
        weight = 1 / class_sample_count
        print("class_sample_count", class_sample_count)
        print("unique_disext",disext_unique_list )
        print("original weight",weight )

        idx_0 = disext_unique_list.index(0)
        weight[idx_0] += 20 * weight[idx_0]
        # samples_weight = np.array([weight[disext_unique_list.index(t)] for t in disext_np])

        # weight_0 = sys_ratio + (1-sys_ratio)/21  # weight for category of 0, which is for original 0 and sys 0
        # weight_others = 1 - weight_0  # weight for other categories
        # # weight = [weight_0, *weight_others]
        # samples_weight = np.array([weight_0 if t==0 else weight_others for t in disext_np])
        print("weight: ", weight)
        # print(samples_weight)
    else:
        weight = 1. / class_sample_count

    samples_weight = np.array([weight[disext_unique_list.index(t)] for t in disext_np])

    # weight = [nb_nonzero/len(data_y_list) if e[0] == 0 else nb_zero/len(data_y_list) for e in data_y_list]
    samples_weight = samples_weight.astype(np.float32)
    samples_weight = torch.from_numpy(samples_weight)
    sampler = WeightedRandomSampler(samples_weight, len(samples_weight))
    print(list(sampler))
    return sampler


def compute_metrics(mypath: PathInit, mypath2=None, log_dict=None):
    """

    Args:
        mypath:
        mypath2:
        log_dict:

    Returns:

    """
    for mode in ['train', 'valid', 'test', 'validaug']:
        if mypath.project_name == 'score':
            label = mypath.label(mode)
            pred = mypath.pred_end5(mode)
        else:
            label = mypath.world(mode)  # compare world metrics makes sure all experiments are compatible
            pred = mypath.pred_world(mode)
        try:
            if (not os.path.isfile(label)) and (mypath2 is not None):
                # mypath2 = Path(eval_id)
                shutil.copytree(mypath2.id_dir, mypath.id_dir, dirs_exist_ok=True)

            out_dt = confusion(label, pred)
            log_dict.update(out_dt)

            icc_ = futil.icc(label, pred)
            log_dict.update(icc_)
        except FileNotFoundError:
            continue
    return log_dict


def get_mae_best(fpath):
    """

    :param fpath:
    :return:
    """
    loss = pd.read_csv(fpath)
    mae = min(loss['mae'].to_list())
    return mae


def eval_net_mae(mypath, mypath_src):
    mypath2 = mypath_src
    shutil.copy(mypath2.model_fpath, mypath.model_fpath)  # make sure there is at least one model there
    for mo in ['train', 'validaug', 'valid', 'test']:
        try:
            shutil.copy(mypath2.loss(mo), mypath.loss(mo))  # make sure there is at least one model
        except FileNotFoundError:
            pass
    valid_mae_best = get_mae_best(mypath2.loss('valid'))
    print(f'load model from {mypath2.model_fpath}, valid_mae_best is {valid_mae_best}')
    return valid_mae_best


def add_best_metrics(df: pd.DataFrame, mypath, mypath2, index: int, args) -> pd.DataFrame:
    modes = ['train', 'validaug', 'valid', 'test']
    if mypath.project_name == 'score':
        metrics_min = 'mae_end5'
    else:
        metrics_min = 'mae'
    df.at[index, 'metrics_min'] = metrics_min

    for mode in modes:
        lock2 = FileLock(mypath.loss(mode) + ".lock")
        # when evaluating/inference old models, those files would be copied to new the folder
        with lock2:
            try:
                loss_df = pd.read_csv(mypath.loss(mode))
            except FileNotFoundError:  # copy loss files from old directory to here

                shutil.copy(mypath2.loss(mode), mypath.loss(mode))
                try:
                    loss_df = pd.read_csv(mypath.loss(mode))
                except FileNotFoundError:  # still cannot find the loss file in old directory, pass this mode
                    continue

            best_index = loss_df[metrics_min].idxmin()
            loss = loss_df['loss'][best_index]
            mae = loss_df['mae'][best_index]
            if mypath.project_name == 'score':
                mae_end5 = loss_df['mae_end5'][best_index]
                df.at[index, mode + '_mae_end5'] = round(mae_end5, 2)
        df.at[index, mode + '_loss'] = round(loss, 2)
        df.at[index, mode + '_mae'] = round(mae, 2)
    return df


def write_and_backup(df: pd.DataFrame, record_file: str, mypath):
    df.to_csv(record_file, index=False)
    shutil.copy(record_file, os.path.join(mypath.results_dir, 'cp_' + os.path.basename(record_file)))
    df_lastrow = df.iloc[[-1]]
    df_lastrow.to_csv(os.path.join(mypath.id_dir, os.path.basename(record_file)), index=False)  # save the record of the current ex


def fill_running(df: pd.DataFrame):
    for index, row in df.iterrows():
        if 'State' not in list(row.index) or row['State'] in [None, np.nan, 'RUNNING']:
            try:
                jobid = row['outfile'].split('-')[-1].split('_')[0]  # extract job id from outfile name
                seff = os.popen('seff ' + jobid)  # get job information
                for line in seff.readlines():
                    line = line.split(
                        ': ')  # must have space to be differentiated from time format 00:12:34
                    if len(line) == 2:
                        key, value = line
                        key = '_'.join(key.split(' '))  # change 'CPU utilized' to 'CPU_utilized'
                        value = value.split('\n')[0]
                        df.at[index, key] = value
            except:
                pass
    return df


def correct_type(df: pd.DataFrame):
    for column in df:
        ori_type = type(df[column].to_list()[-1])  # find the type of the last valuable in this column
        if ori_type is int:
            df[column] = df[column].astype('Int64')  # correct type
    return df


def get_df_id(record_file: str):
    if not os.path.isfile(record_file) or os.stat(record_file).st_size == 0:  # empty?
        new_id = 1
        df = pd.DataFrame()
    else:
        df = pd.read_csv(record_file)  # read the record file,
        last_id = df['ID'].to_list()[-1]  # find the last ID
        new_id = int(last_id) + 1
    return df, new_id


def record_1st(task, args):
    """
    First record in this experiment.
    :param record_file: a file to store super parameters and metrics
    :param args: arguments which need to be saved to record_file
    :return: None
    """
    if task=='score':
        record_file = PathScoreInit().record_file
        from ssc_scoring.mymodules.path import PathScore as Path
    else:
        record_file = PathPosInit().record_file
        from ssc_scoring.mymodules.path import PathPos as Path

    lock = FileLock(record_file + ".lock")  # lock the file, avoid other processes write other things
    with lock:  # with this lock,  open a file for exclusive access
        with open(record_file, 'a') as csv_file:
            df, new_id = get_df_id(record_file)
            if args.mode=='train':
                mypath = Path(new_id, check_id_dir=True)  # to check if id_dir already exist
            else:
                mypath = Path(new_id, check_id_dir=True)

            start_date = datetime.date.today().strftime("%Y-%m-%d")
            start_time = datetime.datetime.now().time().strftime("%H:%M:%S")
            # start record by id, date,time row = [new_id, date, time, ]
            idatime = {'ID': new_id, 'start_date': start_date, 'start_time': start_time}
            args_dict = vars(args)
            idatime.update(args_dict)  # followed by super parameters
            if len(df) == 0:  # empty file
                df = pd.DataFrame([idatime])  # need a [] , or need to assign the index for df
            else:
                index = df.index.to_list()[-1]  # last index
                for key, value in idatime.items():  # write new line
                    df.at[index + 1, key] = value  #

            df = fill_running(df)  # fill the state information for other experiments
            df = correct_type(df)  # aviod annoying thing like: ID=1.00
            write_and_backup(df, record_file, mypath)
    return new_id


def record_2nd(task, current_id, log_dict, args):
    """
    Second time to save logs
    :param record_file:
    :param current_id:
    :param log_dict: containing super parameters
    :param args: used to get metrics
    :return:
    """
    if task=='score':
        record_file = PathScoreInit().record_file
        from ssc_scoring.mymodules.path import PathScore as Path
    else:
        record_file = PathPosInit().record_file
        from ssc_scoring.mymodules.path import PathPos as Path
    lock = FileLock(record_file + ".lock")
    with lock:  # with this lock,  open a file for exclusive access
        df = pd.read_csv(record_file)
        index = df.index[df['ID'] == current_id].to_list()
        if len(index) > 1:
            raise Exception("over 1 row has the same id", id)
        elif len(index) == 0:  # only one line,
            index = 0
        else:
            index = index[0]

        start_date = datetime.date.today().strftime("%Y-%m-%d")
        start_time = datetime.datetime.now().time().strftime("%H:%M:%S")
        df.at[index, 'end_date'] = start_date
        df.at[index, 'end_time'] = start_time

        # usage
        f = "%Y-%m-%d %H:%M:%S"
        t1 = datetime.datetime.strptime(df['start_date'][index] + ' ' + df['start_time'][index], f)
        t2 = datetime.datetime.strptime(df['end_date'][index] + ' ' + df['end_time'][index], f)
        elapsed_time = time_diff(t1, t2)
        df.at[index, 'elapsed_time'] = elapsed_time

        mypath = Path(current_id)  # evaluate old model
        df = add_best_metrics(df, mypath, Path(args.eval_id), index, args)

        for key, value in log_dict.items():  # convert numpy to str before writing all log_dict to csv file
            if type(value) in [np.ndarray, list]:
                str_v = ''
                for v in value:
                    str_v += str(v)
                    str_v += '_'
                value = str_v
            df.loc[index, key] = value
            if type(value) is int:
                df[key] = df[key].astype('Int64')

        for column in df:
            if type(df[column].to_list()[-1]) is int:
                df[column] = df[column].astype('Int64')  # correct type again, avoid None/1.00/NAN, etc.

        args_dict = vars(args)
        args_dict.update({'ID': current_id})
        for column in df:
            if column in args_dict.keys() and type(args_dict[column]) is int:
                df[column] = df[column].astype(float).astype('Int64')  # correct str to float and then int
        write_and_backup(df, record_file, mypath)


def time_diff(t1: datetime, t2: datetime):
    # t1_date = datetime.datetime(t1.year, t1.month, t1.day, t1.hour, t1.minute, t1.second)
    # t2_date = datetime.datetime(t2.year, t2.month, t2.day, t2.hour, t2.minute, t2.second)
    t_elapsed = t2 - t1

    return str(t_elapsed).split('.')[0]  # drop out microseconds


def _bytes_to_megabytes(value_bytes):
    return round((value_bytes / 1024) / 1024, 2)


def record_mem_info():
    ''' Memory usage in kB '''
    with open('/proc/self/status') as f:
        memusage = f.read().split('VmRSS:')[1].split('\n')[0][:-3]
    print('int(memusage.strip())')

    return int(memusage.strip())


def record_GPU_info(outfile):
    """
    Record GPU information to `outfile`.

    The format of `outfile` is: slurm-[JOB_ID].out

    :param outfile:
    :return:

    Example:

    >>> record_GPU_info('slurm-98234.out')

    """
    if outfile:
        jobid_gpuid = outfile.split('-')[-1]
        tmp_split = jobid_gpuid.split('_')[-1]
        if len(tmp_split) == 2:
            gpuid = tmp_split[-1]
        else:
            gpuid = 0
        nvidia_smi.nvmlInit()
        handle = nvidia_smi.nvmlDeviceGetHandleByIndex(gpuid)
        gpuname = nvidia_smi.nvmlDeviceGetName(handle)
        gpuname = gpuname.decode("utf-8")
        # log_dict['gpuname'] = gpuname
        info = nvidia_smi.nvmlDeviceGetMemoryInfo(handle)
        gpu_mem_usage = str(_bytes_to_megabytes(info.used)) + '/' + str(_bytes_to_megabytes(info.total)) + ' MB'
        # log_dict['gpu_mem_usage'] = gpu_mem_usage
        gpu_util = 0
        for i in range(5):
            res = nvidia_smi.nvmlDeviceGetUtilizationRates(handle)
            gpu_util += res.gpu
            time.sleep(1)
        gpu_util = gpu_util / 5
        # log_dict['gpu_util'] = str(gpu_util) + '%'
        return gpuname, gpu_mem_usage, str(gpu_util) + '%'
    else:
        print('outfile is None, can not show GPU memory info')
        return None, None, None

