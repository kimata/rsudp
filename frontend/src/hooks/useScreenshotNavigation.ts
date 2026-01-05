import { useMemo, useCallback } from "react";
import type { Screenshot } from "../types";

export const useScreenshotNavigation = (
    currentImage: Screenshot | null,
    allImages: Screenshot[],
    onNavigate: (screenshot: Screenshot) => void
) => {
    const currentIndex = useMemo(
        () => (currentImage ? allImages.findIndex((img) => img.filename === currentImage.filename) : -1),
        [currentImage, allImages]
    );

    const navigateNext = useCallback(() => {
        if (currentIndex < allImages.length - 1) {
            onNavigate(allImages[currentIndex + 1]);
        }
    }, [currentIndex, allImages, onNavigate]);

    const navigatePrevious = useCallback(() => {
        if (currentIndex > 0) {
            onNavigate(allImages[currentIndex - 1]);
        }
    }, [currentIndex, allImages, onNavigate]);

    return {
        currentIndex,
        navigateNext,
        navigatePrevious,
        canNavigateNext: currentIndex < allImages.length - 1,
        canNavigatePrevious: currentIndex > 0,
        totalCount: allImages.length,
    };
};
