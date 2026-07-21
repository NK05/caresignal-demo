import { describe, expect, it } from "vitest";

import { patientDictionary, patientText } from "./patient-i18n";

describe("patient dictionaries", () => {
  it("keeps matching non-empty keys for English, Shona, and Ndebele", () => {
    const expected = Object.keys(patientDictionary.en).sort();
    for (const language of ["en", "sn", "nd"] as const) {
      expect(Object.keys(patientDictionary[language]).sort()).toEqual(expected);
      expect(Object.values(patientDictionary[language]).every((value) => value.trim())).toBe(true);
    }
  });

  it("selects localized fixed interface text", () => {
    expect(patientText("sn").confirm).toBe("Simbisa uye chengeta");
    expect(patientText("nd").confirm).toBe("Qinisekisa njalo ugcine");
  });
});
