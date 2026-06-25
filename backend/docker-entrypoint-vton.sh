#!/bin/bash
set -e

WEIGHTS_DIR="${VTON_WEIGHTS_DIR:-/app/var/vton_weights}"
EXPECTED_VERSION="${VTON_WEIGHTS_VERSION:-1.5.0}"
VERSION_FILE="${WEIGHTS_DIR}/.version"

needs_download() {
    if [ ! -f "${WEIGHTS_DIR}/model.safetensors" ] \
    || [ ! -f "${WEIGHTS_DIR}/dwpose/yolox_l.onnx" ] \
    || [ ! -f "${WEIGHTS_DIR}/dwpose/dw-ll_ucoco_384.onnx" ]; then
        echo "Файлы весов отсутствуют."
        return 0
    fi
    if [ ! -f "${VERSION_FILE}" ] || [ "$(cat ${VERSION_FILE})" != "${EXPECTED_VERSION}" ]; then
        echo "Версия весов изменилась (ожидается ${EXPECTED_VERSION}, найдено $(cat ${VERSION_FILE} 2>/dev/null || echo 'нет'))."
        return 0
    fi
    return 1
}

if needs_download; then
    echo "Скачиваем веса VTON ${EXPECTED_VERSION} в ${WEIGHTS_DIR}..."
    mkdir -p "${WEIGHTS_DIR}"
    python /opt/fashn-vton/scripts/download_weights.py --weights-dir "${WEIGHTS_DIR}"
    echo "${EXPECTED_VERSION}" > "${VERSION_FILE}"
    echo "Веса скачаны (версия ${EXPECTED_VERSION})."
else
    echo "Веса VTON ${EXPECTED_VERSION} актуальны, пропускаем загрузку."
fi

exec "$@"