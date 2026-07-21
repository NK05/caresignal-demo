export type PatientLanguage = "en" | "sn" | "nd";

export const patientDictionary = {
  en: {
    back: "Patient home", title: "CareSignal conversation", you: "You", careTeam: "Care team",
    template: "CareSignal template", emptyTitle: "Send a home BP reading",
    emptyHelp: "Include both numbers, when you measured, and whether you took your medication. You will confirm before anything is recorded.",
    draft: "AI-extracted draft · not recorded", check: "Check these details", measured: "Measured", medication: "Medication",
    confirm: "Confirm and save", correct: "Correct details", cancel: "Cancel", message: "Message", send: "Send",
    placeholder: "Type a synthetic BP message", pendingPlaceholder: "Confirm, correct, or cancel first",
    safety: "Synthetic data only. This is not an emergency service and does not provide diagnosis or medication changes.",
  },
  sn: {
    back: "Kumba kwemurwere", title: "Hurukuro yeCareSignal", you: "Imi", careTeam: "Chikwata cheutano",
    template: "Meseji yakagadzirirwa neCareSignal", emptyTitle: "Tumirai kuverengwa kweBP yekumba",
    emptyHelp: "Nyorerai manhamba ese, nguva yayakayerwa, uye kana makanwa mushonga. Muchasimbisa pasati pachengetwa chinhu.",
    draft: "Mashoko akabviswa neAI · haasati achengetwa", check: "Tarisai mashoko aya", measured: "Yakayerwa", medication: "Mushonga",
    confirm: "Simbisa uye chengeta", correct: "Gadzirisa mashoko", cancel: "Kanzura", message: "Meseji", send: "Tumira",
    placeholder: "Nyora meseji yeBP yekuedza", pendingPlaceholder: "Tanga wasimbisa, wagadzirisa, kana kukanzura",
    safety: "Mashoko ekuedza chete. Iyi haisi sevhisi yenjodzi uye haiiti kuongorora chirwere kana kushandura mushonga.",
  },
  nd: {
    back: "Ekhaya lesigulane", title: "Ingxoxo yeCareSignal", you: "Wena", careTeam: "Ithimba lezempilakahle",
    template: "Umlayezo olungiswe yiCareSignal", emptyTitle: "Thumela ukubalwa kwe-BP yasekhaya",
    emptyHelp: "Faka amanani womabili, isikhathi olinganise ngaso, lokuthi wawuthatha yini umuthi. Uzaqinisekisa kungakagcinwa lutho.",
    draft: "Okukhitshwe yi-AI · akukagcinwa", check: "Hlola imininingwane le", measured: "Kulinganiswe", medication: "Umuthi",
    confirm: "Qinisekisa njalo ugcine", correct: "Lungisa imininingwane", cancel: "Khansela", message: "Umlayezo", send: "Thumela",
    placeholder: "Bhala umlayezo we-BP wokuzama", pendingPlaceholder: "Qinisekisa, lungisa, kumbe ukhansele kuqala",
    safety: "Idatha yokuzama kuphela. Le kayisiyo isevisi yezimo eziphuthumayo njalo kayihloli isifo kumbe iguqule umuthi.",
  },
} satisfies Record<PatientLanguage, Record<string, string>>;

export function patientText(language: PatientLanguage | undefined) {
  return patientDictionary[language ?? "en"] ?? patientDictionary.en;
}
