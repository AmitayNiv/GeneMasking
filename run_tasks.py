import random
from time import time
import datetime
import numpy as np
import pandas as pd
import torch
import wandb
from data_loading import Data,ImmunData
from test import test,test_xgb
from train import train_G, train_classifier,train_xgb,train_H,train_f2,train_random_forest
from utils import get_mask, get_mask_and_mult,init_models,features_f_corelation,load_datasets_list,save_weights,load_weights
from visualization import visulaize_tsne, visulaize_umap
import os
import copy
import joblib
import xgboost as xgb
import gseapy as gp
from data_loading import Data
from time import time
import datetime
from torch.utils.data import DataLoader
import matplotlib.pyplot as plt


def run_train(args,device):
    ##
    datasets_list = load_datasets_list(args)
    first_data_set = True
    global_time = time()
    for i,f in enumerate(datasets_list):
        first_iteration = True
        dataset_time = time()
        ## Init WandB experiment
        if args.wandb_exp:
            wandb_exp = wandb.init(project="CellAnnotation", entity="niv_a")
            wandb_exp.name = f"Train_{f.name}"
            wandb_exp.config.update(args.__dict__)
        else: 
            wandb_exp = None
        ##

        for j in range(args.iterations):
            res_dict = {}
            res_prints = ""
            iter_time = time()
            # args = arguments()

            # if args.data_type == "immunai":
            #     data = ImmunData(data_set="pbmc",genes_filter="narrow_subset",all_types=False)
            # else:
            data = Data(data_inst=f,train_ratio=args.train_ratio,features=True,all_labels=False)
            print(f"Training iteration:{j} dataset:{data.data_name}")
            
            if args.working_models["F"] or args.working_models["g"]:
                cls,g_model = init_models(args=args,data=data,device=device)
                cls,cls_res_dict = train_classifier(args,device=device,data_obj=data,model=cls,wandb_exp=wandb_exp)
                args.batch_factor=4
                args.weight_decay=0
                g_model ,g_res_dict= train_G(args,device,data_obj=data,classifier=cls,model=g_model,wandb_exp=wandb_exp)

                res_dict.update(cls_res_dict)
                res_dict.update(g_res_dict)
                res_prints+="\nF Resutls\n"
                res_prints+=str(cls_res_dict)
                res_prints+="\nG Resutls\n"
                res_prints+=str(g_res_dict)
                if args.save_weights:
                    save_weights(cls=cls,g=g_model,data=data)

            args.batch_factor=1
            args.weight_decay=5e-4
            if args.working_models["F2_c"]:
                g_model_copy_f2_c = copy.deepcopy(g_model)
                f2_c,g_model_copy_f2_c,f2_c_res_dict = train_f2(args,device,data_obj=data,g_model=g_model_copy_f2_c,wandb_exp=None,model=None,concat=True)
                res_dict.update(f2_c_res_dict)
                res_prints+="\nF2_c Resutls\n"
                res_prints+=str(f2_c_res_dict)
                if args.save_weights:
                    save_weights(cls=f2_c,g=g_model_copy_f2_c,data=data,base="F2_c")
            if args.working_models["F2"]:
                g_model_copy_f2 = copy.deepcopy(g_model)
                f2,g_model_copy_f2,f2_res_dict = train_f2(args,device,data_obj=data,g_model=g_model_copy_f2,wandb_exp=None,model=None,concat=False)
                res_dict.update(f2_res_dict)
                res_prints+="\nF2 Resutls\n"
                res_prints+=str(f2_res_dict)
                if args.save_weights:
                    save_weights(cls=f2,g=g_model_copy_f2,data=data,base="F2")
            if args.working_models["H"]:
                g_model_copy_H = copy.deepcopy(g_model)
                h,g_model_copy_H,h_res_dict = train_H(args,device,data_obj=data,g_model=g_model_copy_H,wandb_exp=None,model=None)
                res_dict.update(h_res_dict)
                res_prints+="\nH Resutls\n"
                res_prints+=str(h_res_dict)
                if args.save_weights:
                    save_weights(cls=h,g=g_model_copy_H,data=data,base="H")
            if args.working_models["XGB"]:
                xgb_cls,xgb_res_dict = train_xgb(data,device)
                res_dict.update(xgb_res_dict)
                res_prints+="\nXGB Resutls\n"
                res_prints+=str(xgb_res_dict)
                if args.save_weights:
                    save_weights(cls=xgb_cls,g=None,data=data,base="XGB")
            
            if args.working_models["RF"]:
                rf_cls,rf_res_dict = train_random_forest(data,device)
                res_dict.update(rf_res_dict)
                res_prints+="\nRF Resutls\n"
                res_prints+=str(rf_res_dict)
                if args.save_weights:
                    save_weights(cls=rf_cls,g=None,data=data,base="RF")


            print(f"############### Results on {data.data_name} ############################")
            print(res_prints)
            print(f"#####################################################################")
            

            if first_iteration:
                single_data_res_df = pd.DataFrame(res_dict, index=[data.data_name])
                first_iteration = False
            else:
                single_res_df = pd.DataFrame(res_dict, index=[data.data_name])
                single_data_res_df = pd.concat([single_data_res_df, single_res_df])
            time_diff = datetime.timedelta(seconds=time()-iter_time)
            print("{}: iteration #{} took {}".format(data.data_name,j+1,time_diff))
            print(f"#################################")
        time_diff = datetime.timedelta(seconds=time()-dataset_time)
        print("{}: {} iterations took {}".format(data.data_name,args.iterations,time_diff))  
        print(f"#################################")     
        single_data_res_mean = pd.DataFrame(single_data_res_df.mean()).T
        single_data_res_mean.index = [data.data_name]
        if first_data_set:
            full_resutls_df = single_data_res_df
            mean_resutls_df = single_data_res_mean
            first_data_set = False
        else:
            full_resutls_df = pd.concat([full_resutls_df, single_data_res_df])
            mean_resutls_df = pd.concat([mean_resutls_df, single_data_res_mean])
            

    time_diff = datetime.timedelta(seconds=time()-global_time)
    print("All training took: {}".format(time_diff))   
    print(f"#################################")  
    time_for_file = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    full_resutls_df.to_csv(f"./results/{time_for_file}_full_res_df.csv")
    if args.iterations>1:
        mean_resutls_df.to_csv(f"./results/{time_for_file}_mean_res_df.csv")


def run_masks_creation(args,device):

    datasets_list = load_datasets_list(args)
    for i,f in enumerate(datasets_list):
        dataset_time = time()
        data = Data(data_inst=f,train_ratio=args.train_ratio,features=True,all_labels=False)
        print(f"Masking dataset:{data.data_name}")
        if not os.path.exists(f"./masks/{data.data_name}/"):
            os.mkdir(f"./masks/{data.data_name}/")
        ###########################################################
        _,g = load_weights(data,device,"")
        mask_df = get_mask(g,data,args,device)


        mask_df[data.colnames] = mask_df[data.colnames].values.astype('float')
        mask_df_mean = mask_df[data.colnames].T.quantile(q=0.2,axis=1)
        mask_df_mean.to_csv(f"./masks/{data.data_name}/G_mask.csv")

        # mask_df_mean = mask_df.groupby(['label'], as_index=False)[data.colnames].mean()
        # mask_df_mean.to_csv(f"./masks/{data.data_name}/G_mask.csv")

        # mask_df_bin= get_mask(g,data,args,device,bin_mask=True)

        # mask_df_bin = mask_df_bin.groupby('label', as_index=False)[data.colnames].mean()
        # mask_df_bin.to_csv(f"./masks/{data.data_name}/G_bin_mask.csv")
        ###########################################################
        _,g = load_weights(data,device,"F2_c")
        mask_df = get_mask(g,data,args,device)

        # mask_df_mean = mask_df.groupby(['label'], as_index=False)[data.colnames].mean()
        mask_df[data.colnames] = mask_df[data.colnames].values.astype('float')
        mask_df_mean = mask_df[data.colnames].T.quantile(q=0.2,axis=1)
        mask_df_mean.to_csv(f"./masks/{data.data_name}/F2_c_mask.csv")

        # mask_df_bin= get_mask(g,data,args,device,bin_mask=True)

        # mask_df_bin = mask_df_bin.groupby('label', as_index=False)[data.colnames].mean()
        # mask_df_bin.to_csv(f"./masks/{data.data_name}/F2_c_bin_mask.csv")
        ###########################################################
        _,g = load_weights(data,device,"F2")
        mask_df = get_mask(g,data,args,device)

        # mask_df_mean = mask_df.groupby(['label'], as_index=False)[data.colnames].mean()
        mask_df[data.colnames] = mask_df[data.colnames].values.astype('float')
        mask_df_mean = mask_df[data.colnames].T.quantile(q=0.2,axis=1)
        mask_df_mean.to_csv(f"./masks/{data.data_name}/F2_mask.csv")

        # mask_df_bin= get_mask(g,data,args,device,bin_mask=True)

        # mask_df_bin = mask_df_bin.groupby('label', as_index=False)[data.colnames].mean()
        # mask_df_bin.to_csv(f"./masks/{data.data_name}/F2_bin_mask.csv")

        

        # ################################################################################################
        # _,g_model_copy_f2_c = load_weights(data,device,"")
        # mask_df = get_mask(g_model_copy_f2_c,data,args,device)

        # mask_df_mean = mask_df.groupby('patient', as_index=False)[data.colnames].mean()
        # mask_df_mean.to_csv(f"./masks/{data.data_name}/G_mask_pat.csv")

        # mask_df_bin= get_mask(g_model_copy_f2_c,data,args,device,bin_mask=True)
        # mask_df_bin = mask_df_bin.groupby('patient', as_index=False)[data.colnames].mean()
        # mask_df_bin.to_csv(f"./masks/{data.data_name}/G_bin_mask_pat.csv")
        ################################################################################################
        time_diff = datetime.timedelta(seconds=time()-dataset_time)
        print("{}:took {}".format(data.data_name,time_diff))  


def run_masks_and_vis(args):
    ## Init random seed
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    ## Conecting to device
    device = torch.device('cuda:2' if torch.cuda.is_available() else 'cpu')
    if device != 'cpu':
        torch.cuda.empty_cache()
    print(f'Using device {device}')
    datasets_list = load_datasets_list(args)
    for i,f in enumerate(datasets_list):
        data = Data(data_inst=f,train_ratio=args.train_ratio,features=True,all_labels=True)
        print(f"Masking dataset:{data.data_name}")
        if not os.path.exists(f"./results/{data.data_name}/"):
            os.mkdir(f"./results/{data.data_name}/")
        _,g_model_copy_f2_c = load_weights(data,device,"F2_c")
        mask_df,mask_x_df,input_df = get_mask_and_mult(g_model_copy_f2_c,data,args,device)
        visulaize_umap(copy.deepcopy(mask_df),"mask_df",data)
        # visulaize_umap(copy.deepcopy(mask_x_df),"mask_x_df",data)
        # visulaize_umap(copy.deepcopy(input_df),"input_df",data)

        # visulaize_tsne(copy.deepcopy(mask_df),"mask_df",data)
        # visulaize_tsne(copy.deepcopy(mask_x_df),"mask_x_df",data)
        # visulaize_tsne(copy.deepcopy(input_df),"input_df",data)


        mask_df,mask_x_df,input_df = get_mask_and_mult(g_model_copy_f2_c,data,args,device,bin_mask=True)

        mask_df_g = mask_df.groupby('patient', as_index=False)[data.colnames].mean()

        visulaize_umap(copy.deepcopy(mask_df),"bin_mask_df",data)
        # visulaize_umap(copy.deepcopy(mask_x_df),"bin_mask_x_df",data)

        # visulaize_tsne(copy.deepcopy(mask_df),"bin_mask_df",data)
        # visulaize_tsne(copy.deepcopy(mask_x_df),"bin_mask_x_df",data)

def run_gsea(args,device):
    datasets_list = load_datasets_list(args)
    # with open("./data/immunai_data_set.gmt")as gmt:
    cols = ["Data","Model","nes","pval","fdr"]
    results_df = pd.DataFrame(columns=cols)
    global_time = time()
    for i,f in enumerate(datasets_list):
        dataset_time = time()
        print(f"\n### Starting work on {f.name[:-5]} ###")
        data = Data(data_inst=f,train_ratio=args.train_ratio,features=True,all_labels=False,test_set=True)
        for mod in ["G","F2_c","F2"]:
            base_print = "" if mod =="G" else mod
            _,g = load_weights(data,device,base_print,only_g=True)
            mask_df = get_mask(g,data,args,device)

            rnk = pd.DataFrame(columns=["0","1"])
            rnk["0"] = data.colnames
            rnk["1"] = mask_df.cpu()
            rnk = rnk.sort_values(by="1",ascending=False)
            pre_res = gp.prerank(rnk=rnk, gene_sets=f'./data/gmt_files/all.gmt',
                    processes=4,
                    permutation_num=100, # reduce number to speed up testing
                    no_plot =True,
                    outdir=f'./results/prerank/{f.name[:-5]}/prerank_report_all', format='png', seed=6,min_size=1, max_size=600)
            res_list = [data.data_name,mod,pre_res.res2d["nes"].values[0],pre_res.res2d["pval"].values[0],pre_res.res2d["fdr"].values[0]]
            single_res_df =pd.DataFrame([res_list],columns=cols)
            results_df = pd.concat([results_df, single_res_df])

        xgb_cls = xgb.XGBClassifier(objective="multi:softproba")
        xgb_cls.load_model(f"./weights/1500_genes_weights/{data.data_name}/XGB.json")
        xgb_rank = pd.DataFrame(columns=["0","1"])
        xgb_rank["0"] = data.colnames
        xgb_rank["1"] = xgb_cls.feature_importances_
        xgb_rank = xgb_rank.sort_values(by="1",ascending=False)
        pre_res_xgb = gp.prerank(rnk=xgb_rank, gene_sets=f'./data/gmt_files/all.gmt',
            processes=4,
            permutation_num=100, # reduce number to speed up testing
            no_plot =True,
            outdir=f'./results/prerank/{f.name[:-5]}/prerank_report_all_xgb', format='png', seed=6,min_size=1, max_size=600)
        res_list = [data.data_name,"XGB",pre_res_xgb.res2d["nes"].values[0],pre_res_xgb.res2d["pval"].values[0],pre_res_xgb.res2d["fdr"].values[0]]
        single_res_df =pd.DataFrame([res_list],columns=cols)
        results_df = pd.concat([results_df, single_res_df])

        ###############################################
        rf_model = joblib.load(f"./weights/1500_genes_weights/{data.data_name}/RF.joblib")
        rf_rank = pd.DataFrame(columns=["0","1"])
        rf_rank["0"] = data.colnames
        rf_rank["1"] = rf_model.feature_importances_
        rf_rank = rf_rank.sort_values(by="1",ascending=False)
        pre_res_rf = gp.prerank(rnk=rf_rank, gene_sets=f'./data/gmt_files/all.gmt',
            processes=4,
            permutation_num=100, # reduce number to speed up testing
            no_plot =True,
            outdir=f'./results/prerank/{f.name[:-5]}/prerank_report_all_rf', format='png', seed=6,min_size=1, max_size=600)
        res_list = [data.data_name,"RF",pre_res_rf.res2d["nes"].values[0],pre_res_rf.res2d["pval"].values[0],pre_res_rf.res2d["fdr"].values[0]]
        single_res_df =pd.DataFrame([res_list],columns=cols)
        results_df = pd.concat([results_df, single_res_df])
        time_diff = datetime.timedelta(seconds=time()-dataset_time)
        print("Working on {}:took {}".format(data.data_name,time_diff))
        print(f"#################################")  

    results_df.to_csv("./results/prerank/prerank_res_df_std.csv")
    time_diff = datetime.timedelta(seconds=time()-global_time)
    print("All training took: {}".format(time_diff))   
    print(f"#################################")  

    


def run_heatmap_procces(args,device):
    datasets_list = load_datasets_list(args)
    for i,f in enumerate(datasets_list):
        dataset_time = time()
        print(f"\n### Starting work on {f.name[:-5]} ###")
        data = Data(data_inst=f,train_ratio=args.train_ratio,features=True,all_labels=False,test_set=True)
        _,g_model = load_weights(data,device,"F2_c",only_g=True)
        dataset_loader = DataLoader(dataset=data.all_dataset,batch_size=len(data.all_dataset)//8,shuffle=False)
        cols = list(data.colnames)
        cols.append("y")
        mask_df = pd.DataFrame(columns=cols)
        print(f"Creating mask for {data.data_name}")
        first_batch = True
        with torch.no_grad():
            g_model.eval()
            for X_batch, y_batch in dataset_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                mask = g_model(X_batch)
                mask.requires_grad = False

                y = np.expand_dims(np.argmax(np.array(y_batch.detach().cpu()),axis=1), axis=1)
                mask = np.concatenate((np.array(mask.detach().cpu()),y),axis=1)
            
                mask_df = pd.concat([mask_df,pd.DataFrame(mask,columns=cols)])
            mask_df= mask_df.reset_index()



            mask_df["label"] = data.named_labels.values
            if hasattr(data,"patient"):
                mask_df["patient"] = data.patient.values




        ten_p = np.quantile(mask_df[data.colnames].values.mean(axis=0),0.9)

        max_patient = data.full_data.obs.patient.value_counts()[:40].index
        mask_df = mask_df[mask_df['patient'].isin(max_patient)]
        mask_df['patient'] = np.array(mask_df['patient'])

        data_types = ["naive CD8","memory CD8","naive CD4","memory CD4"]
        for current_data_name in data_types:
            current_data = mask_df[mask_df["label"]==current_data_name]
            current_data_mean = current_data.groupby("patient")[data.colnames].agg(np.mean)
            current_data_mean.columns = data.colnames
            current_data_std = current_data.groupby("patient")[data.colnames].agg(np.std)
            current_data_std.columns = data.colnames

            # arr = current_data_std.values
            # current_data_mean_mean = current_data_mean.mean(axis=0)
            # best_genes = current_data_mean_mean[current_data_mean_mean>current_data_mean_mean.quantile(0.9)].index
            # arr[current_data_mean.values>ten_p] = current_data_mean.values[current_data_mean.values>ten_p]
            # df = pd.DataFrame(arr,columns=data.colnames)
            current_data_mean_mean = current_data_mean.mean(axis=0)
            best_genes = current_data_mean_mean[current_data_mean_mean>ten_p].index
            df = current_data_mean[best_genes]

            plt.figure(figsize=(30,20))
            plt.imshow(df.values,cmap="hot")
            plt.xticks(np.arange(0.5, len(best_genes), 1), best_genes,rotation = 90)
            plt.yticks(np.arange(0.5, df.shape[0], 1), current_data_mean.index)
            plt.title(current_data_name)
            plt.colorbar()
            plt.savefig(f"./results/heatmap_{current_data_name}.png")



