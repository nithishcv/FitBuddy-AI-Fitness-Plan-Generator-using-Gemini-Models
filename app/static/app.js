document.addEventListener(
    "DOMContentLoaded",
    () => {

        /*
         * Disable the generate button after
         * form submission to prevent accidental
         * duplicate requests.
         */

        const planForm =
            document.querySelector(
                "#plan-form"
            );


        if (planForm) {

            planForm.addEventListener(
                "submit",
                () => {

                    const button =
                        planForm.querySelector(
                            "button[type=submit]"
                        );


                    if (button) {

                        button.disabled =
                            true;

                        button.textContent =
                            "Generating…";
                    }
                }
            );
        }


        /*
         * Disable feedback button after
         * submission.
         */

        document
            .querySelectorAll(
                "form[action='/submit-feedback']"
            )
            .forEach(
                (form) => {

                    form.addEventListener(
                        "submit",
                        () => {

                            const button =
                                form.querySelector(
                                    "button[type=submit]"
                                );


                            if (button) {

                                button.disabled =
                                    true;

                                button.textContent =
                                    "Updating…";
                            }
                        }
                    );
                }
            );

    }
);