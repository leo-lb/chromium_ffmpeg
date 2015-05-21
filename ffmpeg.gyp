# Copyright (c) 2011 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# There's a couple key GYP variables that control how FFmpeg is built:
#   ffmpeg_branding
#     Controls whether we build the Chromium or Google Chrome version of
#     FFmpeg.  The Google Chrome version contains additional codecs.
#     Typical values are Chromium, Chrome, ChromiumOS, and ChromeOS.
#   build_ffmpegsumo
#     When set to zero, will not include ffmpegsumo as a library to be built as
#     part of the larger chrome binary. Default value is 1.
#

{
  'target_defaults': {
    'variables': {
      # Since we are not often debugging FFmpeg, and performance is
      # unacceptable without optimization, freeze the optimizations to -O2.
      # If someone really wants -O1 , they can change these in their checkout.
      # If you want -O0, see the Gotchas in README.Chromium for why that
      # won't work.
      'release_optimize': '2',
      'debug_optimize': '2',
      'mac_debug_optimization': '2',
      # In addition to the above reasons, /Od optimization won't remove symbols
      # that are under "if (0)" style sections.  Which lead to link time errors
      # when for example it tries to link an ARM symbol on X86.
      'win_debug_Optimization': '2',
      # Run time checks are incompatible with any level of optimizations.
      'win_debug_RuntimeChecks': '0',
      'conditions': [
        ['OS == "win"', {
          # Setting the optimizations to 'speed' or to 'max' results in a lot of
          # unresolved symbols. The only supported mode is 'size' (see
          # crbug.com/264459).
          'optimize' :'size',
        }],
      ],
    },
  },
  'variables': {
    # Make sure asm_sources is always defined even if an arch doesn't have any
    # asm sources (e.g. mips or x86 with forcefully disabled asm).
    'asm_sources': [
    ],

    # Allow overriding the selection of which FFmpeg binaries to copy via an
    # environment variable.  Affects the ffmpeg_binaries target.
    'conditions': [
      ['target_arch == "arm" and arm_version == 7 and arm_neon == 1', {
        # Need a separate config for arm+neon vs arm
        'ffmpeg_config%': 'arm-neon',
      }, {
        'ffmpeg_config%': '<(target_arch)',
      }],
      ['OS == "mac" or OS == "win" or OS == "openbsd"', {
        'os_config%': '<(OS)',
      }, {  # all other Unix OS's use the linux config
        'conditions': [
          ['msan==1', {
            # MemorySanitizer doesn't like assembly code.
            'os_config%': 'linux-noasm',
          }, {
            'os_config%': 'linux',
          }]
        ],
      }],
      ['chromeos == 1', {
        'ffmpeg_branding%': '<(branding)OS',
      }, {  # otherwise, assume Chrome/Chromium.
        'ffmpeg_branding%': '<(branding)',
      }],
    ],

    'build_ffmpegsumo%': 1,

    # Locations for generated artifacts.
    'shared_generated_dir': '<(SHARED_INTERMEDIATE_DIR)/third_party/ffmpeg',

    # Stub generator script and signatures of all functions used by Chrome.
    'generate_stubs_script': '../../tools/generate_stubs/generate_stubs.py',
    'sig_files': ['chromium/ffmpegsumo.sigs'],
  },
  'conditions': [
    ['(target_arch == "ia32" or target_arch == "x64") and os_config != "linux-noasm"', {
      'targets': [
        {
          'target_name': 'ffmpeg_yasm',
          'type': 'static_library',
          'includes': [
            'ffmpeg_generated.gypi',
            '../yasm/yasm_compile.gypi',
          ],
          'sources': [
            '<@(asm_sources)',
            # XCode doesn't want to link a pure assembly target and will fail
            # to link when it creates an empty file list.  So add a dummy file
            # keep the linker happy.  See http://crbug.com/157073
            'xcode_hack.c',
          ],
          'variables': {
            # Path to platform configuration files.
            'platform_config_root': 'chromium/config/<(ffmpeg_branding)/<(os_config)/<(ffmpeg_config)',

            'conditions': [
              ['target_arch == "ia32"', {
                'more_yasm_flags': [
                  '-DARCH_X86_32',
                 ],
              }, {
                'more_yasm_flags': [
                  '-DARCH_X86_64',
                ],
              }],
              ['OS == "mac"', {
                'more_yasm_flags': [
                  # Necessary to ensure symbols end up with a _ prefix; added by
                  # yasm_compile.gypi for Windows, but not Mac.
                  '-DPREFIX',
                ]
              }],
            ],
            'yasm_flags': [
              '-DPIC',
              '>@(more_yasm_flags)',
              '-I', '<(platform_config_root)',
              '-I', 'libavcodec/x86/',
              '-I', 'libavutil/x86/',
              '-I', '.',
              # Disable warnings, prevents log spam for things we won't fix.
              '-w',
              '-P', 'config.asm',
            ],
            'yasm_output_path': '<(shared_generated_dir)/yasm'
          },
        },
      ] # targets
    }], # (target_arch == "ia32" or target_arch == "x64")
    ['build_ffmpegsumo == 1', {
      'includes': [
        'ffmpeg_generated.gypi',
        '../../build/util/version.gypi',
      ],
      'variables': {
        # Path to platform configuration files.
        'platform_config_root': 'chromium/config/<(ffmpeg_branding)/<(os_config)/<(ffmpeg_config)',
      },
      'targets': [
        {
          'target_name': 'ffmpegsumo',
          'type': '<(component)',
          'sources': [
            '<@(c_sources)',
            '<(platform_config_root)/config.h',
            '<(platform_config_root)/libavutil/avconfig.h',
          ],
          'include_dirs': [
            '<(platform_config_root)',
            '.',
          ],
          'defines': [
            'HAVE_AV_CONFIG_H',
            '_POSIX_C_SOURCE=200112',
            '_XOPEN_SOURCE=600',
            'PIC',
            # Disable deprecated features which generate spammy warnings.
            'FF_API_PIX_FMT_DESC=0',
            'FF_API_OLD_DECODE_AUDIO=0',
            'FF_API_DESTRUCT_PACKET=0',
            'FF_API_GET_BUFFER=0',
          ],
          'variables': {
            'clang_warning_flags': [
              '-Wno-absolute-value',
              # ffmpeg uses its own deprecated functions.
              '-Wno-deprecated-declarations',
              # ffmpeg doesn't care about pointer constness.
              '-Wno-incompatible-pointer-types',
              # ffmpeg doesn't follow usual parentheses conventions.
              '-Wno-parentheses',
              # ffmpeg doesn't care about pointer signedness.
              '-Wno-pointer-sign',
              # ffmpeg doesn't believe in exhaustive switch statements.
              '-Wno-switch',
              # matroskadec.c has a "failed:" label that's only used if some
              # CONFIG_ flags we don't set are set.
              '-Wno-unused-label',
              # This fires on `av_assert0(!"valid element size")` in utils.c
              '-Wno-string-conversion',
            ],
          },
          'cflags': [
            '-fPIC',
            '-fomit-frame-pointer',
            # ffmpeg uses its own deprecated functions.
            '-Wno-deprecated-declarations',
          ],
          # Silence a warning in libc++ builds (C code doesn't need this flag).
          'ldflags!': [ '-stdlib=libc++', ],
          'conditions': [
            ['(target_arch == "ia32" or target_arch == "x64") and os_config != "linux-noasm"', {
              'dependencies': [
                'ffmpeg_yasm',
              ],
            }],
            ['clang != 1', {
              'cflags': [
                # gcc doesn't have flags for specific warnings, so disable them
                # all.
                '-w',
              ],
            }],
            ['target_arch == "ia32"', {
              # Turn off valgrind build option that breaks ffmpeg builds.
              'cflags!': [
                '-fno-omit-frame-pointer',
              ],
              'debug_extra_cflags!': [
                '-fno-omit-frame-pointer',
              ],
              'release_extra_cflags!': [
                '-fno-omit-frame-pointer',
              ],
            }],  # target_arch == "ia32"
            ['target_arch == "arm"', {
              # TODO(ihf): See the long comment in build_ffmpeg.sh
              # We want to be consistent with CrOS and have configured
              # ffmpeg for thumb. Protect yourself from -marm.
              'cflags!': [
                '-marm',
              ],
              'cflags': [
                '-mthumb',
                '-march=armv7-a',
                '-mtune=cortex-a8',
              ],
              # On arm we use gcc to compile the assembly.
              'sources': [
                '<@(asm_sources)',
              ],
              'conditions': [
                ['arm_neon == 0', {
                  'cflags': [
                    '-mfpu=vfpv3-d16',
                  ],
                }, {
                  'cflags': [
                    '-mfpu=neon',
                  ],
                }],
                ['arm_float_abi == "hard"', {
                  'cflags': [
                    '-DHAVE_VFP_ARGS=1'
                  ],
                }, {
                  'cflags': [
                    '-DHAVE_VFP_ARGS=0'
                  ],
                }],
              ],
            }],
            ['target_arch == "mipsel"', {
              'cflags': [
                '-mips32',
                '-EL -Wl,-EL',
              ],
            }],  # target_arch == "mipsel"
            ['os_posix == 1 and OS != "mac"', {
              'defines': [
                '_ISOC99_SOURCE',
                '_LARGEFILE_SOURCE',
                # BUG(ihf): ffmpeg compiles with this define. But according to
                # ajwong: I wouldn't change _FILE_OFFSET_BITS.  That's a scary change
                # because it affects the default length of off_t, and fpos_t,
                # which can cause strange problems if the loading code doesn't
                # have it set and you start passing FILE*s or file descriptors
                # between symbol contexts.
                # '_FILE_OFFSET_BITS=64',
              ],
              'cflags': [
                '-std=c99',
                '-pthread',
                '-fno-math-errno',
                '-fno-signed-zeros',
                '-fno-tree-vectorize',
              ],
              'link_settings': {
                'ldflags': [
                  '-L<(shared_generated_dir)',
                ],
                'libraries': [
                  '-lm',
                  '-lrt',
                  '-lz',
                ],
              },
            }],  # os_posix == 1 and OS != "mac"
            ['OS == "openbsd"', {
              # OpenBSD's gcc (4.2.1) does not support this flag
              'cflags!': [
                '-fno-signed-zeros',
              ],
            }],
            ['OS == "mac"', {
              'defines': [
                '_DARWIN_C_SOURCE',
              ],
              'conditions': [
                ['mac_breakpad == 1', {
                  'variables': {
                    # A real .dSYM is needed for dump_syms to operate on.
                    'mac_real_dsym': 1,
                  },
                }],
                ['target_arch != "x64"', {
                  # -read_only_relocs cannot be used with x86_64
                  'xcode_settings': {
                    'OTHER_LDFLAGS': [
                      # This is needed because even though FFmpeg now builds
                      # with -fPIC, it's not quite a complete PIC build, only
                      # partial :( Thus we need to instruct the linker to allow
                      # relocations for read-only segments for this target to be
                      # able to generated the shared library on Mac.
                      #
                      # This makes Mark sad, but he's okay with it since it is
                      # isolated to this module. When Mark finds this in the
                      # future, and has forgotten this conversation, this
                      # comment should remind him that the world is still nice
                      # and butterflies still exist...as do rainbows, sunshine,
                      # tulips, etc., etc...but not kittens. Those went away
                      # with this flag.
                      '-Wl,-read_only_relocs,suppress',
                    ],
                  },
                }],
              ],
              'link_settings': {
                'libraries': [
                  '$(SDKROOT)/usr/lib/libz.dylib',
                ],
              },
              'xcode_settings': {
                'DYLIB_INSTALL_NAME_BASE': '@loader_path',
                'LIBRARY_SEARCH_PATHS': [
                  '<(shared_generated_dir)'
                ],
              },
            }],  # OS == "mac"
            ['OS == "win"', {
              # TODO(dalecurtis): We should fix these.  http://crbug.com/154421
              'msvs_disabled_warnings': [
                4996, 4018, 4090, 4305, 4133, 4146, 4554, 4028, 4334, 4101, 4102,
                4116, 4307, 4273, 4005, 4056, 4756,
              ],
              'conditions': [
                ['clang == 1', {
                  'msvs_settings': {
                    'VCCLCompilerTool': {
                      # This corresponds to msvs_disabled_warnings 4273 above.
                      'AdditionalOptions': [ '-Wno-inconsistent-dllimport' ],
                    },
                  },
                }],
                ['clang == 1 or (MSVS_VERSION == "2013" or MSVS_VERSION == "2013e")', {
                  'defines': [
                    'inline=__inline',
                    'strtoll=_strtoi64',
                    '_ISOC99_SOURCE',
                    '_LARGEFILE_SOURCE',
                    'HAVE_AV_CONFIG_H',
                    'strtod=avpriv_strtod',
                    'snprintf=avpriv_snprintf',
                    '_snprintf=avpriv_snprintf',
                    'vsnprintf=avpriv_vsnprintf',
                  ],
                }],
                ['target_arch == "x64"', {
                  # TODO(wolenetz): We should fix this.  http://crbug.com/171009
                  'msvs_disabled_warnings' : [
                    4267
                  ],
                }],
                ['component == "shared_library"', {
                  # Fix warnings about a local symbol being inefficiently imported.
                  'msvs_settings': {
                    'VCCLCompilerTool': {
                      'AdditionalOptions': [
                        '/FIcompat/msvcrt/snprintf.h',
                        '/FIcompat/msvcrt/strtod.h',
                      ],
                    },
                  },
                  'sources': [
                    '<(shared_generated_dir)/ffmpegsumo.def',
                  ],
                  'actions': [
                    {
                      'action_name': 'generate_def',
                      'inputs': [
                        '<(generate_stubs_script)',
                        '<@(sig_files)',
                      ],
                      'outputs': [
                        '<(shared_generated_dir)/ffmpegsumo.def',
                      ],
                      'action': ['python',
                                 '<(generate_stubs_script)',
                                 '-i', '<(INTERMEDIATE_DIR)',
                                 '-o', '<(shared_generated_dir)',
                                 '-t', 'windows_def',
                                 '-m', 'ffmpegsumo.dll',
                                 '<@(_inputs)',
                      ],
                      'message': 'Generating FFmpeg export definitions',
                    },
                  ],
                }],
              ],
            }],
          ],
        },
      ],
    }],
  ],  # conditions
  'targets': [
    {
      'target_name': 'ffmpeg',
      'type': 'none',
      'conditions': [
        ['build_ffmpegsumo == 1', {
          'dependencies': [
              'ffmpegsumo',
            ],
            'direct_dependent_settings': {
            'include_dirs': [
              '../..',  # The chromium 'src' directory.
              '<(platform_config_root)',
              '.',
              ],
            },
          }
        ],
      ],  # conditions
    },
  ],  # targets
}
