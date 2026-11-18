from pythonforandroid.recipe import PyProjectRecipe


class MaterialyoucolorRecipe(PyProjectRecipe):
    # KivyMD 2.0.0 exige materialyoucolor>=3.0.3 (modulo dynamiccolor.color_spec).
    # La receta oficial de p4a usa 2.0.10, por eso se sobreescribe aqui.
    stl_lib_name = "c++_shared"
    version = "3.0.4"
    url = "https://github.com/T-Dynamos/materialyoucolor-python/releases/download/v{version}/materialyoucolor-{version}.tar.gz"


recipe = MaterialyoucolorRecipe()
