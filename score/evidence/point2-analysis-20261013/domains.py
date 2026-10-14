"""仅验证诊断库对应的BF16/TN小输出容量域。"""
import sys
sys.path.insert(0,'/home/developer/cann-general-dispatch-20261013/tests')
import simulator_matrix
simulator_matrix.SHAPES=[('高行单列',1,16,1,56),('双行八列',1,2,8,48),('单行十六列',1,1,16,64),('单行单列',1,1,1,32),('四行四列',1,4,4,64),('五行三列',1,5,3,48),('紧凑全负',1,3,5,40),('紧凑全零',1,3,5,40)]
if __name__=='__main__':simulator_matrix.main()
