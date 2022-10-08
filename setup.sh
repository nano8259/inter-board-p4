mkdir -p ./build && cd ./build
cmake $SDE/p4studio/ \
      -DCMAKE_INSTALL_PREFIX=$SDE_INSTALL \
      -DCMAKE_MODULE_PATH=$SDE/cmake      \
      -DP4_NAME="inter-board"               \
      -DP4_PATH=$HOME/work_space/inter-board/inter-board.p4 \
      -DTOFINO2=on
make inter-board && make install
cd ..
