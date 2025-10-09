window.Fuzzbin = window.Fuzzbin || {};

async function ensureAntiforgeryToken(form) {
    const endpoint = form.dataset.antiforgeryEndpoint || '/antiforgery/token';
    let fieldName = form.dataset.antiforgeryField;
    let tokenInput = fieldName ? form.querySelector(`input[name="${fieldName}"]`) : null;

    if (tokenInput && tokenInput.value) {
        return;
    }

    const response = await fetch(endpoint, {
        method: 'GET',
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
    });

    if (!response.ok) {
        throw new Error('Failed to fetch antiforgery token.');
    }

    const data = await response.json();
    fieldName = data.fieldName || data.formFieldName || fieldName || '__RequestVerificationToken';
    let tokenValue = data.requestToken || data.token;

    if (!tokenValue) {
        throw new Error('Antiforgery token payload missing token value.');
    }

    tokenInput = form.querySelector(`input[name="${fieldName}"]`);
    if (!tokenInput) {
        tokenInput = document.createElement('input');
        tokenInput.type = 'hidden';
        tokenInput.name = fieldName;
        form.appendChild(tokenInput);
    }

    tokenInput.value = tokenValue;
    form.dataset.antiforgeryField = fieldName;
}

window.Fuzzbin.submitForm = async function (formId) {
    await new Promise(resolve => requestAnimationFrame(resolve));

    const form = document.getElementById(formId);
    if (!form) {
        console.warn('Form not found:', formId);
        return;
    }

    if (form.__fzSubmitting) {
        console.debug('Form already submitting, skipping duplicate request.');
        return;
    }

    form.__fzSubmitting = true;

    try {
        await ensureAntiforgeryToken(form);

        if (typeof form.requestSubmit === 'function') {
            form.requestSubmit();
        } else {
            form.submit();
        }
    } catch (error) {
        console.error('Login form submission failed before POST.', error);
        form.__fzSubmitting = false;
    }
};
