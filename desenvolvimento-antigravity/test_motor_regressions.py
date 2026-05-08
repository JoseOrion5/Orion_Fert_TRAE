import unittest

import motor


def _totals(lines):
    out = {}
    for l in lines:
        for k, v in (l.contrib_pct or {}).items():
            out[k] = out.get(k, 0.0) + float(v or 0.0)
    return out


class TestMotorRegressions(unittest.TestCase):
    def test_solubility_text_mapping(self):
        self.assertAlmostEqual(motor._solubility_limit_mass_kg_from_text("Alta", 100.0), 60.0, places=6)
        self.assertAlmostEqual(motor._solubility_limit_mass_kg_from_text("Média", 100.0), 40.0, places=6)
        self.assertAlmostEqual(motor._solubility_limit_mass_kg_from_text("Baixa", 100.0), 25.0, places=6)

    def test_optimization_feasible_n15_mg2(self):
        vol = 100.0
        insumos = [
            motor.Insumo(
                id="U1",
                nome="Ureia (prilled/granular)",
                solubilidade="Alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"N": 45.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            ),
            motor.Insumo(
                id="NA",
                nome="Nitrato de amônio",
                solubilidade="Alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"N": 33.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            ),
            motor.Insumo(
                id="MG",
                nome="Cloreto de Magnésio",
                solubilidade="Alta (solúvel)",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"Mg": 10.0},
                rank_solubilidade=1,
                rank_custo=1,
                preco_unit=1.0,
            ),
        ]

        outs = motor.build_top12_outputs(
            vol,
            {"N": 15.0, "Mg": 2.0},
            insumos,
            [],
            25.0,
            use_optimization=True,
            limite_diversificacao=75.0,
        )
        best = next((o for o in outs if o.lines), None)
        self.assertIsNotNone(best)
        totals = _totals(best.lines)
        self.assertAlmostEqual(totals.get("N", 0.0), 15.0, places=3)
        self.assertAlmostEqual(totals.get("Mg", 0.0), 2.0, places=3)
        self.assertLessEqual(float(best.indice_saturacao or 0.0), 1.0 + 1e-6)

    def test_s_from_so4_equality(self):
        vol = 100.0
        insumos = [
            motor.Insumo(
                id="SA",
                nome="Sulfato de amônio",
                solubilidade="Alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"SO4": 15.0, "N": 21.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            )
        ]

        outs = motor.build_top12_outputs(
            vol,
            {"S": 2.0},
            insumos,
            [],
            25.0,
            use_optimization=True,
            limite_diversificacao=75.0,
        )
        best = next((o for o in outs if o.lines), None)
        self.assertIsNotNone(best)
        totals = _totals(best.lines)
        self.assertAlmostEqual(totals.get("S", 0.0), 2.0, places=3)

    def test_forced_quelante_ca_s(self):
        vol = 100.0
        insumos = [
            motor.Insumo(
                id="CA",
                nome="Nitrato de cálcio",
                solubilidade="Alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"Ca": 10.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            ),
            motor.Insumo(
                id="SA",
                nome="Sulfato de amônio",
                solubilidade="Alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"SO4": 15.0, "N": 21.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            ),
        ]
        edta = motor.Aditivo(
            id="Q",
            grupo="Quelante",
            nome="EDTA",
            abreviatura="EDTA",
            funcao_principal="Quelante",
            nutrientes_compativeis="",
            faixa_ph_ideal="",
            dose_maxima_legal_pct="0.10",
            dose_maxima_tecnica_pct="0.10",
            modo_aplicacao="",
            alerta_incompatibilidade="",
            observacoes="",
            preco_unit=10.0,
        )

        outs = motor.build_top12_outputs(
            vol,
            {"Ca": 2.0, "S": 2.0},
            insumos,
            [edta],
            25.0,
            use_optimization=True,
            limite_diversificacao=75.0,
        )
        best = next((o for o in outs if o.lines), None)
        self.assertIsNotNone(best)
        self.assertTrue(any((a.get("massa_kg") or 0.0) > 0 for a in (best.aditivos or [])))
        self.assertTrue(any((l.fornecedor or "") == "Aditivo" for l in best.lines))

    def test_diversification_cap_enforced(self):
        vol = 100.0
        insumos = [
            motor.Insumo(
                id="A",
                nome="Fonte A",
                solubilidade="Muito alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"N": 20.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            ),
            motor.Insumo(
                id="B",
                nome="Fonte B",
                solubilidade="Muito alta",
                natureza_fisica="Sólida",
                teor_por_nutriente_pct={"N": 20.0},
                rank_solubilidade=3,
                rank_custo=1,
                preco_unit=1.0,
            ),
        ]

        outs = motor.build_top12_outputs(
            vol,
            {"N": 20.0},
            insumos,
            [],
            25.0,
            use_optimization=True,
            limite_diversificacao=60.0,
        )
        best = next((o for o in outs if o.lines), None)
        self.assertIsNotNone(best)
        cap = 20.0 * 0.60
        for l in best.lines:
            self.assertLessEqual(float(l.contrib_pct.get("N", 0.0) or 0.0), cap + 1e-6)


if __name__ == "__main__":
    unittest.main()
