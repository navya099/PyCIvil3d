from pybind11.setup_helpers import Pybind11Extension, build_ext
from setuptools import setup

class NativeBuildExt(build_ext):
    def build_extensions(self):
        version = self.distribution.get_version()
        for extension in self.extensions:
            extension.define_macros.append(("PYCIVIL3D_NATIVE_VERSION", f'"{version}"'))
        super().build_extensions()


setup(
    ext_modules=[
        Pybind11Extension(
            "pycivil3d._core",
            ["cpp/bindings.cpp", "cpp/tin_surface.cpp"],
            cxx_std=17,
        )
    ],
    cmdclass={"build_ext": NativeBuildExt},
)
