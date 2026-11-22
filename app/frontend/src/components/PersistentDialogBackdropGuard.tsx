import { useEffect } from "react";

/**
 * Material UI dialogs often contain long-running forms. Prevent an accidental
 * backdrop click from discarding them while preserving explicit actions and
 * Escape-key handling owned by each dialog.
 */
export function PersistentDialogBackdropGuard() {
    useEffect(() => {
        const preventBackdropDismissal = (event: MouseEvent) => {
            const target = event.target;
            if (!(target instanceof Element)) return;

            const dialogRoot = target.closest(".MuiDialog-root");
            if (!dialogRoot) return;

            const clickedBackdrop = Boolean(target.closest(".MuiBackdrop-root"));
            const clickedOutsidePaper = Boolean(target.closest(".MuiDialog-container"))
                && !target.closest(".MuiDialog-paper");
            if (!clickedBackdrop && !clickedOutsidePaper) return;

            event.preventDefault();
            event.stopPropagation();
        };

        document.addEventListener("click", preventBackdropDismissal, true);
        return () => document.removeEventListener("click", preventBackdropDismissal, true);
    }, []);

    return null;
}
