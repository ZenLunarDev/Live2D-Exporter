# Copyright (c) 2023 Meptl
# Copyright (c) 2026 กรมท
# SPDX-License-Identifier: MIT

from .extension import Live2DExporterExtension

Krita.instance().addExtension(Live2DExporterExtension(Krita.instance()))
