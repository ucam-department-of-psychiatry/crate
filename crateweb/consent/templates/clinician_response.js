{# clinician_response.js #}
{% comment %}
    template parameters:
        option_c_available: "true" or "false"
{% endcomment %}

var c_available = {{ option_c_available }};

function startup() {
    hideAll();
    if (!c_available) {
        document.getElementById("optionC_radio").style.display = (
            "none"
        );
    }
}

function hideAll() {
    document.getElementById("optionR").style.display = "none";
    document.getElementById("optionA").style.display = "none";
    document.getElementById("optionB").style.display = "none";
    document.getElementById("optionC").style.display = "none";
    document.getElementById("optionD").style.display = "none";
    document.getElementById("submit").style.display = "none";
}

function showR() {
    document.getElementById("optionR").style.display = "block";
    document.getElementById("optionA").style.display = "none";
    document.getElementById("optionB").style.display = "none";
    document.getElementById("optionC").style.display = "none";
    document.getElementById("optionD").style.display = "none";
    document.getElementById("submit").style.display = "block";
}

function showA() {
    document.getElementById("optionR").style.display = "none";
    document.getElementById("optionA").style.display = "block";
    document.getElementById("optionB").style.display = "none";
    document.getElementById("optionC").style.display = "none";
    document.getElementById("optionD").style.display = "none";
    document.getElementById("submit").style.display = "block";
}

function showB() {
    document.getElementById("optionR").style.display = "none";
    document.getElementById("optionA").style.display = "none";
    document.getElementById("optionB").style.display = "block";
    document.getElementById("optionC").style.display = "none";
    document.getElementById("optionD").style.display = "none";
    document.getElementById("submit").style.display = "block";
}

function showC() {
    document.getElementById("optionR").style.display = "none";
    document.getElementById("optionA").style.display = "none";
    document.getElementById("optionB").style.display = "none";
    document.getElementById("optionC").style.display = "block";
    document.getElementById("optionD").style.display = "none";
    document.getElementById("submit").style.display = "block";
}

function showD() {
    document.getElementById("optionR").style.display = "none";
    document.getElementById("optionA").style.display = "none";
    document.getElementById("optionB").style.display = "none";
    document.getElementById("optionC").style.display = "none";
    document.getElementById("optionD").style.display = "block";
    document.getElementById("submit").style.display = "block";
}
