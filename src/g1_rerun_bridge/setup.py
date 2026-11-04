from setuptools import find_packages, setup

package_name = "g1_rerun_bridge"

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
    description="Read-only Unitree G1 ROS 2 to Rerun diagnostics bridge.",
    license="MIT",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "bridge = g1_rerun_bridge.bridge:main",
        ],
    },
)
