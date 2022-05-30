import logging
import random

import fire
import fwrench.embeddings as feats
import fwrench.utils.autows as autows
import fwrench.utils.data_settings as settings
import numpy as np
import torch
from sklearn.decomposition import PCA
from wrench.logging import LoggingHandler


def main(
    dataset="mnist",
    dataset_home="./datasets",
    embedding="pca",  # raw | pca | resnet18 | vae
    #
    #
    lf_selector="snuba",  # snuba | interactive | goggles
    em_hard_labels=False,  # Use hard or soft labels for end model training
    n_labeled_points=100,  # Number of points used to train lf_selector
    #
    # Snuba options
    snuba_combo_samples=-1,  # -1 uses all feat. combos
    # TODO this needs to work for Snuba and IWS
    snuba_cardinality=2,  # Only used if lf_selector='snuba'
    snuba_iterations=23,
    lf_class_options="default",  # default | comma separated list of lf classes to use in the selection procedure. Example: 'DecisionTreeClassifier,LogisticRegression'
    #
    # Interactive Weak Supervision options
    iws_iterations=30,
    seed=123,
):

    ################ HOUSEKEEPING/SELF-CARE 😊 ################################
    random.seed(seed)
    logging.basicConfig(
        format="%(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
        handlers=[LoggingHandler()],
    )
    logger = logging.getLogger(__name__)
    device = torch.device("cuda")

    ################ LOAD DATASET #############################################

    if dataset == "mnist":
        train_data, valid_data, test_data, k_cls, model = settings.get_mnist(
            n_labeled_points, dataset_home
        )
    else:
        raise NotImplementedError

    ################ FEATURE REPRESENTATIONS ##################################
    if embedding == "raw":
        embedder = feats.FlattenEmbedding()
    elif embedding == "pca":
        emb = PCA(n_components=100)
        embedder = feats.SklearnEmbedding(emb)
    elif embedding == "resnet18":
        embedder = feats.ResNet18Embedding()
    elif embedding == "vae":
        embedder = VAE2DEmbedding()
    elif embedding == 'clip':
        embedder = CLIPEmbedding()
    elif embedding == 'clip_zeroshot':
        embedder = ZeroShotCLIPEmbedding()
    
        embedder = feats.VAE2DEmbedding()
    elif embedding == "oracle":
        embedder = feats.OracleEmbedding(k_cls)
    else:
        raise NotImplementedError

    embedder.fit(train_data, valid_data, test_data)
    train_data_embed = embedder.transform(train_data)
    valid_data_embed = embedder.transform(valid_data)
    test_data_embed = embedder.transform(test_data)

    ################ AUTOMATED WEAK SUPERVISION ###############################
    if lf_selector == "snuba":
        train_covered, hard_labels, soft_labels = autows.run_snuba(
            valid_data,
            train_data,
            test_data,
            valid_data_embed,
            train_data_embed,
            test_data_embed,
            snuba_cardinality,
            snuba_combo_samples,
            snuba_iterations,
            lf_class_options,
            logger,
        )
    elif lf_selector == "snuba_multiclass":
        raise NotImplementedError
    elif lf_selector == "iws":
        train_covered, hard_labels, soft_labels = autows.run_snuba(
            valid_data,
            train_data,
            test_data,
            valid_data_embed,
            train_data_embed,
            test_data_embed,
            snuba_cardinality,
            snuba_combo_samples,
            iws_iterations,
            lf_class_options,
            logger,
        )
    elif lf_selector == "iws_multiclass":
        raise NotImplementedError
    elif lf_selector == "goggles":
        raise NotImplementedError
    elif lf_selector == "supervised":
        train_covered, hard_labels, soft_labels = autows.run_supervised(
            valid_data,
            train_data,
            test_data,
            valid_data_embed,
            train_data_embed,
            test_data_embed,
            logger,
        )
    else:
        raise NotImplementedError

    ################ TRAIN END MODEL ##########################################
    model.fit(
        dataset_train=train_covered,
        y_train=hard_labels if em_hard_labels else soft_labels,
        dataset_valid=valid_data,
        evaluation_step=50,
        metric="acc",
        patience=1000,
        device=device,
    )
    logger.info(f"---LeNet eval---")
    acc = model.test(test_data, "acc")
    logger.info(f"end model (LeNet) test acc:    {acc}")
    return acc
    ################ PROFIT 🤑 #################################################


if __name__ == "__main__":
    fire.Fire(main)
