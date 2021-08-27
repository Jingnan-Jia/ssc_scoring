import numpy as np
import pandas as pd

from ssc_scoring.mymodules.confusion_test import confusion


def metrics(pred_fpath: str, label_fpath: str, bland_in_1: bool, adap_markersize: bool) -> None:
    """Evaluate the difference between prediction and label.

    :param pred_fpath: Full path for prediction.
    :param label_fpath: Full path for label.
    :param bland_in_1: If plot bland-altman of several columns into one figure.
    :param adap_markersize: If use adaptive markersize.
    :return: None. Metrics results will be writed to disk.

    Example:

    #. Evaluate the performance of human observer:

        >>> label_fpath = "/data/jjia/ssc_scoring/observer_agreement/16_patients/ground_truth_16patients.csv"
        >>> pred_fpath = "/data/jjia/ssc_scoring/observer_agreement/16_patients/LKT2_16patients.csv"
        >>> metrics(pred_fpath, label_fpath, bland_in_1=False, adap_markersize=True)

    #. Evaluate the performance of AI models on 16 patients which were re-scored by human observers:

        >>> label_fpath = "/data/jjia/ssc_scoring/observer_agreement/16_patients/ground_truth_16patients.csv"
        >>> pred_fpath = "/data/jjia/ssc_scoring/1405_16pats_pred.csv" # Prediction from AI models
        >>> metrics(pred_fpath, label_fpath, bland_in_1=False, adap_markersize=True)

    See :py:mod:`ssc_scoring.mymodules.confusion_test` for more detailed examples.
    """
    df_label = pd.read_csv(label_fpath)
    df_pred = pd.read_csv(pred_fpath)

    label_np = df_label.to_numpy()
    pred_np = df_pred.to_numpy()
    diff = pred_np - label_np
    if bland_in_1:
        mean = np.mean(diff)
        std = np.std(diff)
        bland_in_1_mean_std = {"mean": mean, "std": std}
    else:
        bland_in_1_mean_std = None
    confusion(label_fpath, pred_fpath, bland_in_1_mean_std=bland_in_1_mean_std, adap_markersize=adap_markersize)


if __name__ == "__main__":
    pred_fpath = "/data/jjia/ssc_scoring/observer_agreement/16_patients/LKT2_16patients.csv"
    # pred_fpath = "/data/jjia/ssc_scoring/1405_16pats_pred.csv"
    label_fpath = "/data/jjia/ssc_scoring/observer_agreement/16_patients/ground_truth_16patients.csv"
    bland_in_1 = False
    adap_markersize = True
    metrics(pred_fpath, label_fpath, bland_in_1, adap_markersize)
