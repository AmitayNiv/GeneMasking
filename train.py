import torch
import torch.nn as nn
import numpy as np
import torch.optim as optim
from torch.utils.data import DataLoader
import copy
import xgboost as xgb
from tqdm import tqdm


from models import Classifier,G_Model
from metrics import evaluate


def train_classifier(args,device,data_obj,model,wandb_exp):
    print("Start training classifier")
    train_losses = []
    val_losses =[]
    best_model_auc = 0


    train_loader = DataLoader(dataset=data_obj.train_dataset,batch_size=args.batch_size)
    val_loader = DataLoader(dataset=data_obj.val_dataset, batch_size=len(data_obj.val_dataset))
    test_loader = DataLoader(dataset=data_obj.test_dataset, batch_size=len(data_obj.test_dataset))



    criterion = nn.CrossEntropyLoss()#(weight=data_obj.class_weights.to(device))
    optimizer = optim.Adam(model.parameters(), lr=args.cls_lr,weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=float(args.cls_lr), steps_per_epoch=len(train_loader)//args.batch_factor+1, epochs=args.cls_epochs)

    if args.wandb_exp:
        wandb_exp.config.update({"num_of_features":data_obj.n_features,"num_of_classes":data_obj.number_of_classes,"n_train":data_obj.train_samples.shape[0],
        "n_val":data_obj.val_samples.shape[0],"n_test":data_obj.test_samples.shape[0]})





    global_step = 0
    for e in range(args.cls_epochs):
        model.train()
        train_loss = 0
        # with tqdm(total=len(train_loader), desc=f'Epoch {e + 1}/{args.cls_epochs}', unit='vec') as pbar:
        for X_train_batch, y_train_batch in train_loader:
            X_train_batch, y_train_batch = X_train_batch.to(device), y_train_batch.to(device)
            

            y_train_pred = model(X_train_batch)
            loss = criterion(y_train_pred, y_train_batch)
            loss.backward()

            
            if (global_step + 1) % args.batch_factor == 0:
                optimizer.step()
                optimizer.zero_grad()
                scheduler.step()

            
            train_loss += loss.item()

            global_step += 1
            # pbar.update(X_train_batch.shape[0])
            # pbar.set_postfix(**{'loss (batch)': loss.item()})
        else:
            val_loss = 0
        
            with torch.no_grad():
                model.eval()
                val_epoch_loss = 0
                for X_val_batch, y_val_batch in val_loader:
                    X_val_batch, y_val_batch = X_val_batch.to(device), y_val_batch.to(device)
                    y_val_pred = model(X_val_batch)     
                    val_loss = criterion(y_val_pred, y_val_batch)
                    val_epoch_loss += val_loss.item()
                    val_score = evaluate(y_val_batch, y_val_pred)

    
                    
            # train_losses.append(train_loss/len(train_batch))
            # val_losses.append(val_loss)

            print("Epoch: {}/{}.. ".format(e+1, args.cls_epochs),
                "Training Loss: {:.5f}.. ".format(train_loss/len(train_loader)),
                "Val mAUC: {:.5f}.. ".format(val_score["mauc"]),
                "Val medAUC: {:.5f}.. ".format(val_score["med_auc"]),
                "Val mAUPR: {:.5f}.. ".format(val_score["maupr"]),
                "Val wegAUPR: {:.5f}.. ".format(val_score["weight_aupr"]),
                "Val medAUPR: {:.5f}.. ".format(val_score["med_aupr"]),
                "Val ACC: {:.5f}.. ".format(val_score["accuracy"]))
            
            if args.wandb_exp:
                wandb_exp.log({"epoch":e+1,"train loss":train_loss/len(train_loader),"Val mAUC":val_score["mauc"],"Val medAUC":val_score["med_auc"],
                "Val mAUPR":val_score["maupr"],"Val wegAUPR":val_score["weight_aupr"],"Val medAUPR":val_score["med_aupr"],
                "Val Accuracy":val_score["accuracy"],"lr":optimizer.state_dict()["param_groups"][0]["lr"]
                })

            if val_score["mauc"] >best_model_auc:
                best_model_auc = val_score["mauc"]
                best_model_res = val_score.copy()
                best_model_index = e+1
                # best_model_name = "/F_model_{:.3f}.pt".format(best_model_auc)
                # best_model_path = current_folder+best_model_name
                print("Model Saved, Auc ={:.4f} , Epoch ={}".format(best_model_auc,best_model_index))
                # torch.save(model,best_model_path)
                best_model = copy.deepcopy(model)
            # scheduler.step(val_score["auc"])
    if args.wandb_exp:
        wandb_exp.log({"Val mAUC":best_model_res["mauc"],"Val medAUC":best_model_res["med_auc"],
        "Val mAUPR":best_model_res["maupr"],"Val wegAUPR":best_model_res["weight_aupr"],"Val medAUPR":best_model_res["med_aupr"],"Val Accuracy":best_model_res["accuracy"]
        })
    best_model = best_model.to(device)
    with torch.no_grad():
        best_model.eval()
        for X_test_batch, y_test_batch in test_loader:
            X_test_batch, y_test_batch = X_test_batch.to(device), y_test_batch.to(device)
            y_pred_score = best_model(X_test_batch)
            test_score = evaluate(y_test_batch, y_pred_score)
            print("Classifier test results:")
            print(test_score)
        if args.wandb_exp:
            wandb_exp.config.update({"Test mAUC":test_score["mauc"],"Test medAUC":test_score["med_auc"],
            "Test mAUPR":test_score["maupr"],"Test wegAUPR":test_score["weight_aupr"],"Test medAUPR":test_score["med_aupr"],"Test Accuracy":test_score["accuracy"]
            })
    return best_model


def train_G(args,device,data_obj,classifier,model=None,wandb_exp=None):
    print("Start training G model")
    classifier.eval()

    train_losses = []
    val_losses_list =[]
    best_model_auc = 0



    train_loader = DataLoader(dataset=data_obj.train_dataset,batch_size=args.batch_size)
    val_loader = DataLoader(dataset=data_obj.val_dataset, batch_size=len(data_obj.val_dataset))
    test_loader = DataLoader(dataset=data_obj.test_dataset, batch_size=len(data_obj.test_dataset))

    criterion = nn.CrossEntropyLoss()#weight=data_obj.class_weights.to(device))
    optimizer_G = optim.Adam(model.parameters(), lr=args.g_lr,weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer_G,max_lr=float(args.g_lr),steps_per_epoch=len(train_loader)//args.batch_factor+1, epochs=args.g_epochs)


    if args.wandb_exp:
        wandb_exp.config.update({"num_of_features":data_obj.n_features,"num_of_classes":data_obj.number_of_classes,"n_train":data_obj.train_samples.shape[0],
        "n_val":data_obj.val_samples.shape[0],"n_test":data_obj.test_samples.shape[0]})

    global_step = 0
    for e in range(args.g_epochs):
        classifier.eval()
        # with tqdm(total=len(train_loader), desc=f'Epoch {e + 1}/{args.g_epochs}', unit='vec') as pbar:
        train_loss = 0
        loss_list = []
        model.train()
        for X_train_batch, y_train_batch in train_loader:
            X_train_batch, y_train_batch = X_train_batch.to(device), y_train_batch.to(device)
            mask = model(X_train_batch)
            cropped_features = X_train_batch * mask
            output = classifier(cropped_features)
            loss = criterion(output, y_train_batch) + mask.mean()
            loss.backward()
            
            if (global_step + 1) % args.batch_factor == 0:
                optimizer_G.step()
                optimizer_G.zero_grad(set_to_none=True)
                scheduler.step()
            train_loss += loss.item()

            # pbar.update(X_train_batch.shape[0])
            # pbar.set_postfix(**{'loss (batch)': loss.item()})
            global_step +=1
        else:
            val_losses = 0
        
            with torch.no_grad():
                model.eval()
                classifier.eval()
                val_epoch_loss = 0
                for X_val_batch, y_val_batch in val_loader:
                    X_val_batch, y_val_batch = X_val_batch.to(device), y_val_batch.to(device)
                    mask_val = model(X_val_batch)   
                    print("mask mean = {:.5f}, max= {:.5f}, min = {:.5f}".format(mask_val.mean(),mask_val.max(),mask_val.min()))
                    cropped_features = X_val_batch * mask_val
                    output = classifier(cropped_features)
                    val_loss = criterion(output, y_val_batch) + mask_val.mean()
                    val_losses +=  val_loss.item()

                    val_score = evaluate(y_val_batch, output)
                print("Epoch: {}/{}.. ".format(e+1,  args.g_epochs),
                "Training Loss: {:.5f}.. ".format(train_loss/len(train_loader)),
                "Val Loss: {:.5f}.. ".format(val_losses/len(val_loader)),
                "Val mAUC: {:.5f}.. ".format(val_score["mauc"]),
                "Val medAUC: {:.5f}.. ".format(val_score["med_auc"]),
                "Val mAUPR: {:.5f}.. ".format(val_score["maupr"]),
                "Val wegAUPR: {:.5f}.. ".format(val_score["weight_aupr"]),
                "Val medAUPR: {:.5f}.. ".format(val_score["med_aupr"]),
                "Val ACC: {:.5f}.. ".format(val_score["accuracy"]))

                if args.wandb_exp:
                    wandb_exp.log({"epoch":e+1,"G train loss":train_loss/len(train_loader),"G Val mAUC":val_score["mauc"],"G Val medAUC":val_score["med_auc"],
                    "G Val mAUPR":val_score["maupr"],"G Val wegAUPR":val_score["weight_aupr"],"G Val medAUPR":val_score["med_aupr"],
                    "G Val Accuracy":val_score["accuracy"],"lr":optimizer_G.state_dict()["param_groups"][0]["lr"]
                    })
                if val_score["mauc"] >best_model_auc:
                    best_model_auc = val_score["mauc"]
                    best_model_res = val_score.copy()
                    best_model_index = e+1
                    print("Model Saved,Epoch = {}".format(best_model_index))
                    best_G_model = copy.deepcopy(model)
                    # torch.save(model,best_model_path)	
    if args.wandb_exp:
        wandb_exp.log({"G Val mAUC":best_model_res["mauc"],"G Val medAUC":best_model_res["med_auc"],
        "G Val mAUPR":best_model_res["maupr"],"G Val wegAUPR":best_model_res["weight_aupr"],
        "G Val medAUPR":best_model_res["med_aupr"],"G Val Accuracy":best_model_res["accuracy"]
        })   
    with torch.no_grad():
        best_G_model.eval()
        classifier.eval()
        for X_test_batch, y_test_batch in test_loader:
            X_test_batch, y_test_batch = X_test_batch.to(device), y_test_batch.to(device)
            print(f"############### Results on {data_obj.data_name} ############################")
            print("Results without G")
            y_pred_score = classifier(X_test_batch)
            cls_test_score = evaluate(y_test_batch,y_pred_score)
            print(cls_test_score)
            print("Results with G")
            mask_test = best_G_model(X_test_batch)
            cropped_features = X_test_batch * mask_test
            y_pred_score = classifier(cropped_features)
            test_score = evaluate(y_test_batch, y_pred_score)
            print(test_score)
        if args.wandb_exp:
            wandb_exp.config.update({"G Test mAUC":test_score["mauc"],"G Test medAUC":test_score["med_auc"],
            "G Test mAUPR":test_score["maupr"],"G Test wegAUPR":test_score["weight_aupr"],
            "G Test medAUPR":test_score["med_aupr"],"G Test Accuracy":test_score["accuracy"]
            })
        res_dict = {"Test mAUC":cls_test_score["mauc"],"Test medAUC":cls_test_score["med_auc"],
            "Test mAUPR":cls_test_score["maupr"],"Test wegAUPR":cls_test_score["weight_aupr"],"Test medAUPR":cls_test_score["med_aupr"],
            "Test Accuracy":cls_test_score["accuracy"],
            "G Test mAUC":test_score["mauc"],"G Test medAUC":test_score["med_auc"],
            "G Test mAUPR":test_score["maupr"],"G Test wegAUPR":test_score["weight_aupr"],
            "G Test medAUPR":test_score["med_aupr"],"G Test Accuracy":test_score["accuracy"]
            }
    return best_G_model, res_dict


def train_H(args,device,data_obj,g_model,model=None,wandb_exp=None):
    print("Start training H classifier")
    train_losses = []
    val_losses =[]
    best_model_auc = 0


    train_loader = DataLoader(dataset=data_obj.train_dataset,batch_size=args.batch_size)
    val_loader = DataLoader(dataset=data_obj.val_dataset, batch_size=len(data_obj.val_dataset))
    test_loader = DataLoader(dataset=data_obj.test_dataset, batch_size=len(data_obj.test_dataset))


    if model == None:
        model = Classifier(data_obj.n_features ,dropout=args.dropout,number_of_classes=data_obj.number_of_classes)
        model = model.to(device)
    criterion = nn.CrossEntropyLoss()#weight=data_obj.class_weights.to(device))
    optimizer = optim.Adam(model.parameters(), lr=args.cls_lr)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer,max_lr=float(args.cls_lr), steps_per_epoch=len(train_loader)//args.batch_factor+1, epochs=args.cls_epochs)




    global_step = 0
    g_model.to(device)
    
    for e in range(args.cls_epochs):
        g_model.eval()
        model.train()
        train_loss = 0
        # with tqdm(total=len(train_loader), desc=f'Epoch {e + 1}/{args.cls_epochs}', unit='vec') as pbar:
        for X_train_batch, y_train_batch in train_loader:
            X_train_batch, y_train_batch = X_train_batch.to(device), y_train_batch.to(device)
            
            mask = g_model(X_train_batch)
            y_train_pred = model(mask)
            loss = criterion(y_train_pred, y_train_batch)
            loss.backward()

            
            if (global_step + 1) % args.batch_factor == 0:
                optimizer.step()
                optimizer.zero_grad()
                scheduler.step()

            
            train_loss += loss.item()

            global_step += 1
            # pbar.update(X_train_batch.shape[0])
            # pbar.set_postfix(**{'loss (batch)': loss.item()})
        else:
            val_loss = 0
        
            with torch.no_grad():
                model.eval()
                g_model.eval()
                val_epoch_loss = 0
                for X_val_batch, y_val_batch in val_loader:
                    X_val_batch, y_val_batch = X_val_batch.to(device), y_val_batch.to(device)
                    mask = g_model(X_val_batch)
                    y_val_pred = model(mask) 
                    val_loss = criterion(y_val_pred, y_val_batch)
                    val_epoch_loss += val_loss.item()
                    val_score = evaluate(y_val_batch, y_val_pred)

    
                    
            # train_losses.append(train_loss/len(train_batch))
            # val_losses.append(val_loss)

            print("Epoch: {}/{}.. ".format(e+1, args.cls_epochs),
                "Training Loss: {:.5f}.. ".format(train_loss/len(train_loader)),
                "Val mAUC: {:.5f}.. ".format(val_score["mauc"]),
                "Val medAUC: {:.5f}.. ".format(val_score["med_auc"]),
                "Val mAUPR: {:.5f}.. ".format(val_score["maupr"]),
                "Val wegAUPR: {:.5f}.. ".format(val_score["weight_aupr"]),
                "Val medAUPR: {:.5f}.. ".format(val_score["med_aupr"]),
                "Val ACC: {:.5f}.. ".format(val_score["accuracy"]))
            if val_score["mauc"] >best_model_auc:
                best_model_auc = val_score["mauc"]
                best_model_index = e+1
                # best_model_name = "/F_model_{:.3f}.pt".format(best_model_auc)
                # best_model_path = current_folder+best_model_name
                print("Model Saved, Auc ={:.4f} , Epoch ={}".format(best_model_auc,best_model_index))
                # torch.save(model,best_model_path)
                best_model = copy.deepcopy(model)
            # scheduler.step(val_score["auc"])

    best_model = best_model.to(device)
    with torch.no_grad():
        best_model.eval()
        g_model.eval()
        for X_test_batch, y_test_batch in test_loader:
            X_test_batch, y_test_batch = X_test_batch.to(device), y_test_batch.to(device)
            mask = g_model(X_test_batch)
            y_pred_score = best_model(mask)
            test_score = evaluate(y_test_batch, y_pred_score)
            print("Classifier test results:")
            print(test_score)
    return best_model


def train_xgb(data_obj,device):
    print("Start training XGBoost")
    xgb_cl = xgb.XGBClassifier(objective="multi:softproba")
    X_train = np.array(data_obj.train_dataset.X_data)
    y_train = np.array(data_obj.train_dataset.y_data)
    y_train = np.argmax(y_train,axis=1)
    xgb_cl.fit(X_train, y_train)

    print(f"XGB Test Results on {data_obj.data_name}")
    X_test = np.array(data_obj.test_dataset.X_data)
    y_test = np.array(data_obj.test_dataset.y_data)
    y_pred_score =  xgb_cl.predict_proba(X_test)
    y_pred_score = torch.from_numpy(y_pred_score).to(device)
    test_score = evaluate(y_test,y_pred_score)
    print(test_score)
    res_dict = {"XGB mAUC":test_score["mauc"],"XGB medAUC":test_score["med_auc"],
            "XGB mAUPR":test_score["maupr"],"XGB wegAUPR":test_score["weight_aupr"],"XGB medAUPR":test_score["med_aupr"],
            "XGB Accuracy":test_score["accuracy"]}
    return xgb_cl,res_dict


