from setuptools import find_packages, setup

package_name = "g1_rerun_dex"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools", "rerun-sdk", "numpy"],
    zip_safe=True,
    maintainer="sriramk",
    maintainer_email="sriramk@example.com",
    description="Read-only Unitree G1 Dex3 tactile diagnostics in Rerun.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "dex_rerun = g1_rerun_dex.dex_rerun:main",
        ],
    },
)
