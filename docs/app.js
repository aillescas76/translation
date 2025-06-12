document.addEventListener('DOMContentLoaded', () => {
    const pageImage = document.getElementById('page-image');
    const translatedText = document.getElementById('translated-text');
    const prevButton = document.getElementById('prev-button');
    const nextButton = document.getElementById('next-button');
    const pageIndicator = document.getElementById('page-indicator');

    let manifest = null;
    let currentPageIndex = 0;

    function init() {
        // Check if the viewerData object exists (it's loaded from viewer-data.js)
        if (typeof viewerData !== 'undefined' && viewerData.pages && viewerData.pages.length > 0) {
            manifest = viewerData;
            loadPage(currentPageIndex);
        } else {
            displayError("Could not load viewer data. Please run the 'create-viewer-data' step in the Python script first to generate 'viewer/viewer-data.js'.");
        }
    }

    function loadPage(index) {
        if (!manifest || !manifest.pages[index]) {
            return;
        }

        const pageData = manifest.pages[index];
        
        // Update image using the path from the data file
        pageImage.src = pageData.image;

        // Update text directly from the data object
        translatedText.textContent = pageData.translation || "No translated text found for this page.";

        updateControls();
    }

    function updateControls() {
        const totalPages = manifest.pages.length;
        pageIndicator.textContent = `Page ${currentPageIndex + 1} / ${totalPages}`;

        prevButton.disabled = currentPageIndex === 0;
        nextButton.disabled = currentPageIndex >= totalPages - 1;
    }
    
    function displayError(message) {
        const mainContent = document.querySelector('main');
        mainContent.innerHTML = `<div class="col-span-full bg-red-900 border border-red-700 text-white p-6 rounded-lg text-center">${message}</div>`;
        prevButton.disabled = true;
        nextButton.disabled = true;
        pageIndicator.textContent = "Error";
    }

    prevButton.addEventListener('click', () => {
        if (currentPageIndex > 0) {
            currentPageIndex--;
            loadPage(currentPageIndex);
        }
    });

    nextButton.addEventListener('click', () => {
        if (manifest && currentPageIndex < manifest.pages.length - 1) {
            currentPageIndex++;
            loadPage(currentPageIndex);
        }
    });

    init();
});
