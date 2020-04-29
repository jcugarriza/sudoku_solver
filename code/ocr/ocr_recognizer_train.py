
import imgaug.augmenters as iaa
import numpy as np
from tensorflow.keras import losses
from tensorflow.keras.callbacks import ModelCheckpoint, EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import Input, MaxPooling2D
from tensorflow.keras.layers import (
    concatenate,
    Conv2D,
    Conv2DTranspose,
    GlobalMaxPool2D,
    Dense
)
from pathlib import Path
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam

from generate_samples import get_char_img

batch_size = 32
input_shape = (32, 32)


def get_recognizer():

    i = 4
    inputs = Input((None, None, 3))

    conv1 = Conv2D(2**i, 3, padding="same", activation="selu")(inputs)
    conv1 = Conv2D(2**i, 3, padding="same", activation="selu")(conv1)
    pool1 = MaxPooling2D(pool_size=(2, 2))(conv1)

    conv2 = Conv2D(2*2**i, 3, padding="same", activation="selu")(pool1)
    conv2 = Conv2D(2*2**i, 3, padding="same", activation="selu")(conv2)
    pool2 = MaxPooling2D(pool_size=(2, 2))(conv2)

    conv3 = Conv2D(4*2**i, 3, padding="same", activation="selu")(pool2)
    conv3 = Conv2D(4*2**i, 3, padding="same", activation="selu")(conv3)
    pool3 = GlobalMaxPool2D()(conv3)

    d_out = Dense(10, activation="softmax")(pool3)

    model = Model(inputs=[inputs], outputs=[d_out])

    model.compile(
        optimizer=Adam(lr=3e-4),
        loss=losses.sparse_categorical_crossentropy,
        metrics=["acc"],
    )

    model.summary()

    return model


def get_seq():
    sometimes = lambda aug: iaa.Sometimes(0.3, aug)
    seq = iaa.Sequential(
        [
            sometimes(iaa.AdditiveGaussianNoise(scale=0.07 * 255)),
            sometimes(iaa.GaussianBlur(sigma=(0, 3.0))),
            sometimes(iaa.MedianBlur(k=(3, 11))),
            sometimes(iaa.AverageBlur(k=((5, 11), (1, 3)))),
            sometimes(iaa.AveragePooling([2, 8])),
            sometimes(iaa.MaxPooling([2, 8])),
            sometimes(iaa.Sequential([iaa.Resize({"height": 64, "width": 64}),
                                      iaa.Resize({"height": input_shape[0], "width": input_shape[1]})])),
            sometimes(iaa.Sequential([iaa.Resize({"height": 16, "width": 16}),
                                      iaa.Resize({"height": input_shape[0], "width": input_shape[1]})])),

        ],
        random_order=True,
    )
    return seq


def gen(size=32, fonts_path="ttf", augment=True):
    seq = get_seq()

    fonts_paths = [str(x) for x in Path(fonts_path).glob("*.otf")] +\
                  [str(x) for x in Path(fonts_path).glob("*.ttf")]

    while True:

        samples = [get_char_img(fonts_paths=fonts_paths) for _ in range(size)]
        list_images, list_gt = zip(*samples)

        if augment:
            list_images = seq.augment_images(images=list_images)

        array_gt = np.array(list_gt)[..., np.newaxis]

        yield np.array(list_images), array_gt


if __name__ == "__main__":
    model_h5 = "ocr_recognizer.h5"

    print("Model : %s" % model_h5)

    model = get_recognizer()

    try:
        model.load_weights(model_h5, by_name=True)
    except:
        pass

    checkpoint = ModelCheckpoint(
        model_h5, monitor="acc", verbose=1, save_best_only=True, mode="max"
    )
    early = EarlyStopping(monitor="acc", mode="max", patience=1000, verbose=1)
    redonplat = ReduceLROnPlateau(
        monitor="acc", mode="max", patience=20, verbose=1, min_lr=1e-7
    )
    callbacks_list = [checkpoint, early, redonplat]

    history = model.fit_generator(
        gen(),
        epochs=2000,
        verbose=1,
        steps_per_epoch=128,
        validation_data=gen(augment=False),
        validation_steps=64,
        callbacks=callbacks_list,
        # use_multiprocessing=True,
        # workers=8,
    )

    model.save_weights(model_h5)
