from sklearn import metrics
import torch
import torch.nn.functional as F
import numpy as np

def evaluate(y_test, y_pred_score):
    with torch.no_grad():
        y_pred_score = torch.softmax(y_pred_score, dim = 1)
        _, y_pred_tags = torch.max(y_pred_score, dim = 1)
        y_pred = F.one_hot(y_pred_tags,num_classes = y_test.shape[1])
        try:
            y_test = y_test.cpu()
        except:
            pass
        y_pred = y_pred.cpu()
        accuracy = metrics.accuracy_score(y_test, y_pred)

        aucs = []
        auprs = []
        for cls in range(y_pred_score.shape[1]):
            aupr = metrics.average_precision_score(y_test[:,cls], y_pred_score[:,cls].detach().cpu())
            fpr, tpr, _ = metrics.roc_curve(y_test[:,cls], y_pred_score[:,cls].detach().cpu(), pos_label=1)
            aucs.append(metrics.auc(fpr, tpr))
            auprs.append(aupr)
        
        auc = metrics.roc_auc_score(y_test, y_pred_score.detach().cpu(),multi_class='ovr')
        auprs_weighted = metrics.average_precision_score(y_test, y_pred_score.detach().cpu(),average="weighted")
        

        score = {}
        score['accuracy'] = accuracy
        score['mauc'] = np.nanmean(aucs)
        score['med_auc'] = np.nanmedian(aucs)
        score['maupr'] = np.nanmean(auprs)
        score['weight_aupr'] = auprs_weighted
        score['med_aupr'] = np.nanmedian(auprs)
        assert auc == score['mauc']
        # assert auprs_weighted == score['maupr']
        return score