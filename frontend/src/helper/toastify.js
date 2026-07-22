import { toast } from "react-toastify";

const toastStyles = {
    style: {
        backgroundColor: "#2e2720",
        color: "#DEC39B",
        border: "1px solid #DEC39B",
        borderRadius: "8px",
    },
    progressStyle: {
        backgroundColor: "#DEC39B",
    },
};

const defaultOptions = {
    position: "top-center",
    autoClose: 2500,
    hideProgressBar: false,
    closeOnClick: true,
    pauseOnHover: false,
    draggable: false,
    ...toastStyles,
};

export const showToast = {

    addToCart: (itemName) => {
        toast.success(`${itemName} sepete eklendi!`, {
            ...defaultOptions,
            icon: "🛒",
        });
    },

    removeFromCart: (itemName) => {
        toast.info(`${itemName} sepetten çıkarıldı.`, {
            ...defaultOptions,
            icon: "🗑️",
        });
    },

    success: (message) => {
        toast.success(message, {
            ...defaultOptions,
            icon: "✅",
        });
    },

    error: (message) => {
        toast.error(message, {
            ...defaultOptions,
            style: {
                ...toastStyles.style,
                border: "1px solid #c0392b",
            },
            progressStyle: {
                backgroundColor: "#c0392b",
            },
            icon: "❌",
        });
    },

    warning: (message) => {
        toast.warning(message, {
            ...defaultOptions,
            style: {
                ...toastStyles.style,
                border: "1px solid #F57C00",
            },
            progressStyle: {
                backgroundColor: "#F57C00",
            },
            icon: "⚠️",
        });
    },

    info: (message) => {
        toast.info(message, {
            ...defaultOptions,
            icon: "ℹ️",
        });
    },

};
